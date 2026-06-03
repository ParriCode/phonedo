import asyncio
import contextlib
import glob
import inspect
import json
import os
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional, Literal

import serial

from bleak import BleakScanner


Transport = Literal["BLE", "RFCOMM"]


@dataclass(frozen=True)
class BluetoothObservation:
    mac: str
    sensor_id: str
    value: str
    transport: Transport 
    observation_property : str  = "unknown"
    device_id: str = ""
    device_type: str = "bluetooth"
    procedure: str = ""
    feature_of_interest: str = ""
    unit: str | None = None
    source: str = ""   # Ej: /dev/rfcomm0, manufacturer:76, service:xxxx...


class BluetoothDeviceManager:
    def __init__(
        self,
        on_measurement: Callable[[BluetoothObservation], None | Awaitable[None]],
        transports: set[Transport] | None = None,
        scan_timeout_seconds: float = 2.0,
        ble_sleep_seconds: float = 0.5,

        rfcomm_glob: str = "/dev/rfcomm*",
        rfcomm_ports: list[str] | None = None,
        rfcomm_devices: dict[str, dict] | None = None,
        rfcomm_baudrate: int = 9600,
        rfcomm_read_timeout: float = 1.0,
        rfcomm_poll_seconds: float = 1.0,
        rfcomm_reconnect_seconds: float = 2.0,
    ):
        """
        on_measurement:
            callback que recibirá BluetoothObservation.

        transports:
            {"BLE"}, {"RFCOMM"} o {"BLE", "RFCOMM"}.
            Si no se pasa, usa ambos.

        rfcomm_ports:
            lista explícita de puertos permitidos.
            Ej: ["/dev/rfcomm0", "/dev/rfcomm1"]
            Si es None, acepta todos los /dev/rfcomm*.

        rfcomm_devices:
            metadatos opcionales por puerto.
            Ej:
            {
                "/dev/rfcomm0": {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "sensor_id": "temperatura_1",
                }
            }
        """

        self.on_measurement = on_measurement
        self.transports = transports or {"BLE", "RFCOMM"}

        self.scan_timeout_seconds = scan_timeout_seconds
        self.ble_sleep_seconds = ble_sleep_seconds

        self.rfcomm_glob = rfcomm_glob
        self.rfcomm_ports = set(rfcomm_ports) if rfcomm_ports else None
        self.rfcomm_devices = rfcomm_devices or {}
        self.rfcomm_baudrate = rfcomm_baudrate
        self.rfcomm_read_timeout = rfcomm_read_timeout
        self.rfcomm_poll_seconds = rfcomm_poll_seconds
        self.rfcomm_reconnect_seconds = rfcomm_reconnect_seconds

        self._running = False
        self._main_tasks: list[asyncio.Task] = []
        self._rfcomm_reader_tasks: dict[str, asyncio.Task] = {}

    async def start(self):
        self._running = True
        self._main_tasks = []

        if "BLE" in self.transports:
            self._main_tasks.append(
                asyncio.create_task(self._ble_scan_loop())
            )

        if "RFCOMM" in self.transports:
            self._main_tasks.append(
                asyncio.create_task(self._rfcomm_watch_loop())
            )

        if not self._main_tasks:
            raise RuntimeError("No hay transports activos. Usa {'BLE'}, {'RFCOMM'} o ambos.")

        await asyncio.gather(*self._main_tasks)

    async def stop(self):
        self._running = False

        tasks = [
            *self._main_tasks,
            *self._rfcomm_reader_tasks.values(),
        ]

        for task in tasks:
            task.cancel()

        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._main_tasks.clear()
        self._rfcomm_reader_tasks.clear()

    async def _emit(self, observation: BluetoothObservation):
        result = self.on_measurement(observation)

        if inspect.isawaitable(result):
            await result

    # ============================================================
    # BLE
    # ============================================================

    async def _ble_scan_loop(self):
        while self._running:
            try:
                discovered = await BleakScanner.discover(
                    timeout=self.scan_timeout_seconds,
                    return_adv=True,
                )

                for mac, pair in discovered.items():
                    device, adv = pair
                    mac = mac.strip().lower()

                    observations = self.parse_ble_advertisement(mac, adv)

                    for observation in observations:
                        await self._emit(observation)

            except Exception as e:
                print(f"[BLE] Error escaneando: {e}")

            await asyncio.sleep(self.ble_sleep_seconds)

    def parse_ble_advertisement(self, mac, adv) -> list[BluetoothObservation]:
        observations: list[BluetoothObservation] = []

        # Datos de fabricante
        for manufacturer_id, payload in adv.manufacturer_data.items():
            observations.append(
                BluetoothObservation(
                    mac=mac,
                    sensor_id=f"manufacturer:{manufacturer_id}",
                    value=payload.hex(),
                    transport="BLE",
                    source=f"manufacturer:{manufacturer_id}",
                )
            )

        # Datos de servicio BLE
        for service_uuid, payload in adv.service_data.items():
            observations.append(
                BluetoothObservation(
                    mac=mac,
                    sensor_id=f"service:{service_uuid}",
                    value=payload.hex(),
                    transport="BLE",
                    source=f"service:{service_uuid}",
                )
            )

        return observations

    # ============================================================
    # RFCOMM
    # ============================================================

    async def _rfcomm_watch_loop(self):
        while self._running:
            ports = self._get_existing_rfcomm_ports()

            for port in ports:
                task = self._rfcomm_reader_tasks.get(port)

                if task is None or task.done():
                    print(f"[RFCOMM] Detectado {port}. Arrancando lector.")
                    self._rfcomm_reader_tasks[port] = asyncio.create_task(
                        self._rfcomm_reader_loop(port)
                    )

            # Limpieza de tareas de puertos que ya no existen
            for port, task in list(self._rfcomm_reader_tasks.items()):
                if port not in ports and task.done():
                    self._rfcomm_reader_tasks.pop(port, None)

            await asyncio.sleep(self.rfcomm_poll_seconds)

    def _get_existing_rfcomm_ports(self) -> list[str]:
        ports = sorted(glob.glob(self.rfcomm_glob))

        if self.rfcomm_ports is not None:
            ports = [
                port for port in ports
                if port in self.rfcomm_ports
            ]

        return ports

    async def _rfcomm_reader_loop(self, port: str):
        while self._running:
            if not os.path.exists(port):
                await asyncio.sleep(self.rfcomm_poll_seconds)
                continue

            ser: Optional[serial.Serial] = None

            try:
                print(f"[RFCOMM] Abriendo {port}")

                ser = serial.Serial(
                    port=port,
                    baudrate=self.rfcomm_baudrate,
                    timeout=self.rfcomm_read_timeout,
                )

                print(f"[RFCOMM] Conectado a {port}")

                while self._running and os.path.exists(port):
                    try:
                        raw = await asyncio.to_thread(ser.readline)

                        if not raw:
                            continue

                        observations = self.parse_rfcomm_message(port, raw)

                        for observation in observations:
                            await self._emit(observation)

                    except serial.SerialException as e:
                        print(f"[RFCOMM] Error leyendo {port}: {e}")
                        break

                    except OSError as e:
                        print(f"[RFCOMM] Error del sistema en {port}: {e}")
                        break

            except serial.SerialException as e:
                print(f"[RFCOMM] No se pudo abrir {port}: {e}")

            finally:
                if ser is not None:
                    with contextlib.suppress(Exception):
                        ser.close()

                print(f"[RFCOMM] Cerrado {port}")

            await asyncio.sleep(self.rfcomm_reconnect_seconds)

    def parse_rfcomm_message(
        self,
        port: str,
        raw: bytes,
    ) -> list[BluetoothObservation]:
        """
        Parser por defecto para mensajes RFCOMM.

        Acepta tres formatos:

        1. JSON:
           {"sensor_id": "temp1", "value": "24.5"}

        2. Texto con separador:
           temp1:24.5

        3. Texto plano:
           24.5
        """

        text = raw.decode(errors="replace").strip()

        if not text:
            return []

        metadata = self.rfcomm_devices.get(port, {})

        mac :str = metadata.get("mac", "unknown")
        mac = mac.strip().lower()
        default_sensor_id = metadata.get("sensor_id", port)
        default_device_id = str(metadata.get("device_id", ""))
        default_device_type = str(metadata.get("device_type", "bluetooth"))
        default_observable_property = str(metadata.get("observable_property", "unknown"))
        default_procedure = str(metadata.get("procedure", ""))
        default_feature_of_interest = str(metadata.get("feature_of_interest", ""))
        default_unit = metadata.get("unit", None)

        # Formato JSON
        try:
            obj = json.loads(text)

            if isinstance(obj, dict):
                sensor_id = str(obj.get("sensor_id", obj.get("sensorId", default_sensor_id)))
                value = str(obj.get("value", obj.get("raw_value", obj.get("rawValue", obj))))
                msg_mac = obj.get("mac") or obj.get("mac_address") or obj.get("macAddress") or mac

                return [
                    BluetoothObservation(
                        mac=str(msg_mac).strip().lower(),
                        sensor_id=sensor_id,
                        value=value,
                        transport="RFCOMM",
                        observation_property=str(obj.get("observable_property", obj.get("observableProperty", obj.get("observation_property", default_observable_property)))),
                        device_id=str(obj.get("device_id", obj.get("deviceId", default_device_id))),
                        device_type=str(obj.get("device_type", obj.get("deviceType", default_device_type))),
                        procedure=str(obj.get("procedure", default_procedure)),
                        feature_of_interest=str(obj.get("feature_of_interest", obj.get("featureOfInterest", default_feature_of_interest))),
                        unit=obj.get("unit", default_unit),
                        source=port,
                    )
                ]

        except json.JSONDecodeError:
            pass

        # Formato tipo sensor_id:valor
        if ":" in text:
            sensor_id, value = text.split(":", 1)

            return [
                BluetoothObservation(
                    mac=mac,
                    sensor_id=sensor_id.strip(),
                    value=value.strip(),
                    transport="RFCOMM",
                    observation_property=default_observable_property,
                    device_id=default_device_id,
                    device_type=default_device_type,
                    procedure=default_procedure,
                    feature_of_interest=default_feature_of_interest,
                    unit=default_unit,
                    source=port,
                )
            ]

        # Formato plano
        return [
            BluetoothObservation(
                mac=mac,
                sensor_id=default_sensor_id,
                value=text,
                transport="RFCOMM",
                observation_property=default_observable_property,
                device_id=default_device_id,
                device_type=default_device_type,
                procedure=default_procedure,
                feature_of_interest=default_feature_of_interest,
                unit=default_unit,
                source=port,
            )
        ]
