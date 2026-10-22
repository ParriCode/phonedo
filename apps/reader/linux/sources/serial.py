import asyncio
import contextlib
import glob
import inspect
import json
import os
from datetime import datetime, timezone
from typing import Awaitable, Callable

import serial

from logger import Logger
from reader_core.observation import Observation


class SerialSource:
    def __init__(
        self,
        on_measurement: Callable[[Observation], None | Awaitable[None]],
        port_glob: str = "/dev/rfcomm*",
        ports: list[str] | None = None,
        devices: dict[str, dict] | None = None,
        sensors: dict[str, dict] | None = None,
        baudrate: int = 9600,
        read_timeout: float = 1.0,
        poll_seconds: float = 1.0,
        reconnect_seconds: float = 2.0,
    ):
        self.on_measurement = on_measurement
        self.port_glob = port_glob
        self.ports = set(ports) if ports else None
        self.devices = devices or {}
        self.sensors = sensors or {}
        self.baudrate = baudrate
        self.read_timeout = read_timeout
        self.poll_seconds = poll_seconds
        self.reconnect_seconds = reconnect_seconds
        self._running = False
        self._watch_task: asyncio.Task | None = None
        self._reader_tasks: dict[str, asyncio.Task] = {}

    async def start(self):
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        await self._watch_task

    async def stop(self):
        self._running = False
        tasks = [task for task in [self._watch_task, *self._reader_tasks.values()] if task]

        for task in tasks:
            task.cancel()

        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._watch_task = None
        self._reader_tasks.clear()

    async def _emit(self, observation: Observation):
        result = self.on_measurement(observation)
        if inspect.isawaitable(result):
            await result

    async def _watch_loop(self):
        while self._running:
            ports = self._ports()

            for port in ports:
                task = self._reader_tasks.get(port)
                if task is None or task.done():
                    self._reader_tasks[port] = asyncio.create_task(self._reader_loop(port))

            for port in set(self._reader_tasks) - set(ports):
                task = self._reader_tasks[port]
                if task.done():
                    self._reader_tasks.pop(port, None)

            await asyncio.sleep(self.poll_seconds)

    def _ports(self) -> list[str]:
        ports = sorted(glob.glob(self.port_glob))
        return [port for port in ports if self.ports is None or port in self.ports]

    async def _reader_loop(self, port: str):
        while self._running:
            if not os.path.exists(port):
                await asyncio.sleep(self.poll_seconds)
                continue

            try:
                with serial.Serial(port=port, baudrate=self.baudrate, timeout=self.read_timeout) as serial_port:
                    Logger.info("serial_port_opened", port=port, baudrate=self.baudrate)
                    while self._running and os.path.exists(port):
                        raw = await asyncio.to_thread(serial_port.readline)
                        for observation in self.parse_serial_message(port, raw):
                            await self._emit(observation)
            except (serial.SerialException, OSError) as error:
                Logger.error("serial_port_read_failed", port=port, error=str(error))
                await asyncio.sleep(self.reconnect_seconds)

    def parse_serial_message(self, port: str, raw: bytes) -> list[Observation]:
        text = raw.decode(errors="replace").strip()
        if not text:
            return []

        Logger.info("serial_message_received", port=port, raw=text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"value": text}
        else:
            if not isinstance(data, dict):
                data = {"value": text}

        allowed_keys = {"device_id", "sensor_id", "value", "observable_property", "procedure", "feature_of_interest", "unit"}
        if not isinstance(data, dict) or "value" not in data or set(data) - allowed_keys:
            Logger.error("serial_message_discarded", port=port, reason="invalid_format", raw=text)
            return []

        config = self._config_for(port, data)
        if self._conflicts(config.get("port"), port):
            Logger.error("serial_message_discarded", port=port, reason="port_conflict", expectedPort=config.get("port"), sensorId=config.get("sensor_id"), deviceId=config.get("device_id"))
            return []

        device_id = str(data.get("device_id") or config.get("device_id") or "")
        sensor_id = str(data.get("sensor_id") or config.get("sensor_id") or port)

        if self._blocked(config, "device_id", device_id, "allow_conflicts"):
            Logger.error("serial_message_discarded", port=port, reason="device_conflict", deviceId=device_id)
            return []

        if self._blocked(config, "sensor_id", sensor_id, "sensor_allow_conflicts"):
            Logger.error("serial_message_discarded", port=port, reason="sensor_conflict", sensorId=sensor_id)
            return []

        if not config.get("sensor_allow_conflicts", False) and any(
            self._conflicts(config.get(key), data.get(key))
            for key in ("observable_property", "procedure", "feature_of_interest", "unit")
        ):
            Logger.error("serial_message_discarded", port=port, reason="metadata_conflict", sensorId=sensor_id)
            return []

        sensor_changed = self._conflicts(config.get("sensor_id"), sensor_id)
        Logger.info("serial_observation_parsed", port=port, deviceId=device_id, sensorId=sensor_id, value=data["value"])
        return [
            Observation(
                observable_property=self._field(data, config, "observable_property", "unknown", sensor_changed),
                simple_result=str(data["value"]),
                phenomenon_time=datetime.now(timezone.utc),
                feature_of_interest=self._field(data, config, "feature_of_interest", "", sensor_changed),
                procedure=self._field(data, config, "procedure", "", sensor_changed),
                device_id=device_id,
                sensor_id=sensor_id,
                unit=data.get("unit") if "unit" in data else None if sensor_changed else config.get("unit"),
            )
        ]

    def _config_for(self, port: str, data: dict) -> dict:
        port_config = self.devices.get(port)
        sensor_id = data.get("sensor_id")

        if sensor_id:
            sensor_config = self.sensors.get(str(sensor_id))
            if not sensor_config:
                return port_config or {}
            if port_config and not sensor_config.get("device_id"):
                return {**port_config, **sensor_config, "device_id": data.get("device_id") or port_config.get("device_id")}
            return sensor_config

        if port_config is not None:
            return port_config

        portable = [sensor for sensor in self.sensors.values() if not sensor.get("device_id")]
        if len(portable) == 1 and not data.get("device_id"):
            return portable[0]

        return {}

    def _blocked(self, config: dict, key: str, value: str, allow_key: str) -> bool:
        if (key == "device_id" and config.get("reader_static")) or (key == "sensor_id" and config.get("static")):
            return self._conflicts(config.get(key), value)

        return not config.get(allow_key, False) and self._conflicts(config.get(key), value)

    def _field(self, data: dict, config: dict, key: str, default: str, sensor_changed: bool) -> str:
        if key in data:
            return str(data[key] or default)
        if sensor_changed:
            return default
        return str(config.get(key, default) or default)

    def _conflicts(self, configured, received) -> bool:
        if configured is None or received is None:
            return False

        configured = str(configured).strip()
        received = str(received).strip()
        return bool(configured and received and configured.lower() != received.lower())
