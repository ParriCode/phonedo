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

            except Exception:
                pass

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
                ser = serial.Serial(
                    port=port,
                    baudrate=self.rfcomm_baudrate,
                    timeout=self.rfcomm_read_timeout,
                )

                while self._running and os.path.exists(port):
                    try:
                        raw = await asyncio.to_thread(ser.readline)

                        if not raw:
                            continue

                        observations = self.parse_rfcomm_message(port, raw)

                        for observation in observations:
                            await self._emit(observation)

                    except serial.SerialException:
                        break

                    except OSError:
                        break

            except serial.SerialException:
                pass

            finally:
                if ser is not None:
                    with contextlib.suppress(Exception):
                        ser.close()

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
        configured_sensor_id = metadata.get("sensor_id", "")
        default_sensor_id = configured_sensor_id or port
        default_device_id = str(metadata.get("device_id") or "")
        default_device_type = str(metadata.get("device_type") or "bluetooth")
        default_observable_property = str(metadata.get("observable_property") or "unknown")
        default_procedure = str(metadata.get("procedure") or "")
        default_feature_of_interest = str(metadata.get("feature_of_interest") or "")
        default_unit = metadata.get("unit", None)
        allow_device_conflicts = bool(metadata.get("allow_conflicts", False))
        allow_sensor_conflicts = bool(metadata.get("sensor_allow_conflicts", False))
        device_static = bool(metadata.get("static", False))
        reader_static = bool(metadata.get("reader_static", False))

        # Formato JSON
        try:
            obj = json.loads(text)

            if isinstance(obj, dict):
                sensor_id = str(obj.get("sensor_id", obj.get("sensorId", default_sensor_id)))
                value = str(obj.get("value", obj.get("raw_value", obj.get("rawValue", obj))))
                msg_mac = obj.get("mac") or obj.get("mac_address") or obj.get("macAddress")
                sensor_id_conflicts = self._conflicts(configured_sensor_id, obj.get("sensor_id", obj.get("sensorId", None)))
                device_id_conflicts = self._conflicts(default_device_id, obj.get("device_id", obj.get("deviceId", None)))
                sensor_has_metadata = self._has_sensor_metadata(obj)
                semantic_default = "unknown" if sensor_id_conflicts else default_observable_property
                procedure_default = "" if sensor_id_conflicts else default_procedure
                feature_default = "" if sensor_id_conflicts else default_feature_of_interest
                unit_default = None if sensor_id_conflicts else default_unit

                if self._conflicts(mac, msg_mac):
                    return []

                if reader_static and device_id_conflicts:
                    return []

                if device_static and sensor_id_conflicts:
                    return []

                if (
                    not allow_device_conflicts
                    and (
                        device_id_conflicts
                        or self._conflicts(default_device_type, obj.get("device_type", obj.get("deviceType", None)))
                    )
                ):
                    return []

                if (
                    not allow_sensor_conflicts
                    and (
                        (sensor_id_conflicts and not sensor_has_metadata)
                        or (
                            not sensor_id_conflicts
                            and (
                                self._conflicts(default_observable_property, obj.get("observable_property", obj.get("observableProperty", obj.get("observation_property", None))))
                                or self._conflicts(default_procedure, obj.get("procedure", None))
                                or self._conflicts(default_feature_of_interest, obj.get("feature_of_interest", obj.get("featureOfInterest", None)))
                                or self._conflicts(default_unit, obj.get("unit", None))
                            )
                        )
                    )
                ):
                    return []

                return [
                    BluetoothObservation(
                        mac=str(msg_mac or mac).strip().lower(),
                        sensor_id=sensor_id,
                        value=value,
                        transport="RFCOMM",
                        observation_property=str(obj.get("observable_property", obj.get("observableProperty", obj.get("observation_property", semantic_default)))),
                        device_id=str(obj.get("device_id", obj.get("deviceId", default_device_id))),
                        device_type=str(obj.get("device_type", obj.get("deviceType", default_device_type))),
                        procedure=str(obj.get("procedure", procedure_default)),
                        feature_of_interest=str(obj.get("feature_of_interest", obj.get("featureOfInterest", feature_default))),
                        unit=obj.get("unit", unit_default),
                        source=port,
                    )
                ]

        except json.JSONDecodeError:
            pass

        # Formato tipo sensor_id:valor
        if ":" in text:
            sensor_id, value = text.split(":", 1)
            sensor_id = sensor_id.strip()

            if (
                not allow_sensor_conflicts
                and self._conflicts(configured_sensor_id, sensor_id)
            ):
                return []

            sensor_id_conflicts = self._conflicts(configured_sensor_id, sensor_id)

            if device_static and sensor_id_conflicts:
                return []

            return [
                BluetoothObservation(
                    mac=mac,
                    sensor_id=sensor_id,
                    value=value.strip(),
                    transport="RFCOMM",
                    observation_property="unknown" if sensor_id_conflicts else default_observable_property,
                    device_id=default_device_id,
                    device_type=default_device_type,
                    procedure="" if sensor_id_conflicts else default_procedure,
                    feature_of_interest="" if sensor_id_conflicts else default_feature_of_interest,
                    unit=None if sensor_id_conflicts else default_unit,
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

    def _conflicts(self, configured, received) -> bool:
        if received is None:
            return False

        configured = "" if configured is None else str(configured).strip()
        received = str(received).strip()

        if not configured or not received:
            return False

        if configured.lower() in {"unknown", "unknown-feature", "configured-measurement"}:
            return False

        return configured.lower() != received.lower()

    def _has_sensor_metadata(self, obj: dict) -> bool:
        observable_property = (
            obj.get("observable_property")
            or obj.get("observableProperty")
            or obj.get("observation_property")
        )
        return bool(observable_property and obj.get("procedure"))
