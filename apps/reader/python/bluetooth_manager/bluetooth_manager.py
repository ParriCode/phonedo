import asyncio
import contextlib
import inspect
from datetime import datetime, timezone
from typing import Awaitable, Callable

from bleak import BleakScanner

from logger import Logger
from reader_core.observation import Observation


class BluetoothDeviceManager:
    def __init__(
        self,
        on_measurement: Callable[[Observation], None | Awaitable[None]],
        scan_timeout_seconds: float = 2.0,
        sleep_seconds: float = 0.5,
    ):
        self.on_measurement = on_measurement
        self.scan_timeout_seconds = scan_timeout_seconds
        self.sleep_seconds = sleep_seconds

        self._running = False
        self._scan_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._scan_task = asyncio.create_task(self._ble_scan_loop())
        await self._scan_task

    async def stop(self):
        self._running = False

        if self._scan_task is None:
            return

        self._scan_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await self._scan_task

        self._scan_task = None

    async def _emit(self, observation: Observation):
        result = self.on_measurement(observation)

        if inspect.isawaitable(result):
            await result

    async def _ble_scan_loop(self):
        while self._running:
            try:
                discovered = await BleakScanner.discover(
                    timeout=self.scan_timeout_seconds,
                    return_adv=True,
                )
                Logger.info("bluetooth_scan_completed", devices=len(discovered))

                for device_id, pair in discovered.items():
                    _device, adv = pair
                    device_id = device_id.strip().lower()

                    observations = self.parse_ble_advertisement(device_id, adv)

                    for observation in observations:
                        await self._emit(observation)

            except Exception as error:
                Logger.error("bluetooth_scan_failed", error=str(error))

            await asyncio.sleep(self.sleep_seconds)

    def parse_ble_advertisement(self, device_id, adv) -> list[Observation]:
        observations: list[Observation] = []

        for manufacturer_id, payload in adv.manufacturer_data.items():
            Logger.info("bluetooth_observation_parsed", deviceId=device_id, sensorId=f"manufacturer:{manufacturer_id}")
            observations.append(
                Observation(
                    observable_property="unknown",
                    simple_result=payload.hex(),
                    phenomenon_time=datetime.now(timezone.utc),
                    feature_of_interest="unknown",
                    procedure="unknown",
                    device_id=device_id,
                    sensor_id=f"manufacturer:{manufacturer_id}",
                )
            )

        for service_uuid, payload in adv.service_data.items():
            Logger.info("bluetooth_observation_parsed", deviceId=device_id, sensorId=f"service:{service_uuid}")
            observations.append(
                Observation(
                    observable_property="unknown",
                    simple_result=payload.hex(),
                    phenomenon_time=datetime.now(timezone.utc),
                    feature_of_interest="unknown",
                    procedure="unknown",
                    device_id=device_id,
                    sensor_id=f"service:{service_uuid}",
                )
            )

        return observations
