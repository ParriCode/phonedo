from __future__ import annotations

import importlib.util
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import Any

import pybind11
import requests


ROOT_DIR = Path(__file__).resolve().parents[3]
CORE_DIR = ROOT_DIR / "apps/reader/core"
CPP_SRC = CORE_DIR / "src"
BINDING_SRC = CORE_DIR / "bindings/pybind_reader_core.cpp"
BUILD_DIR = Path(__file__).resolve().parent / ".cpp_build"
EXT_SUFFIX = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
MODULE_PATH = BUILD_DIR / f"_phonendo_reader_core{EXT_SUFFIX}"


def _build_module() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    sources = [
        BINDING_SRC,
        CPP_SRC / "core.cpp",
        CPP_SRC / "device.cpp",
        CPP_SRC / "sensor.cpp",
        CPP_SRC / "obsevation.cpp",
        CPP_SRC / "serializer.cpp",
    ]
    if MODULE_PATH.exists() and all(MODULE_PATH.stat().st_mtime >= source.stat().st_mtime for source in sources):
        return

    subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            "-shared",
            "-fPIC",
            f"-I{CPP_SRC}",
            f"-I{pybind11.get_include()}",
            f"-I{sysconfig.get_paths()['include']}",
            *[str(source) for source in sources],
            "-o",
            str(MODULE_PATH),
        ],
        check=True,
    )


def _load_native():
    _build_module()
    spec = importlib.util.spec_from_file_location("_phonendo_reader_core", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_native = _load_native()

Device = _native.Device
Sensor = _native.Sensor
Observation = _native.Observation
_NativeReaderCore = _native._NativeReaderCore
serialize_sosa_ttl = _native.serialize_sosa_ttl


def _device_from_config(json_data: dict, default_device_id: str | None = None) -> Device:
    device_id = json_data.get("device_id") or default_device_id
    device = Device(
        str(device_id),
        str(json_data.get("device_type") or json_data.get("deviceType") or "device"),
        platform=str(json_data["platform"]) if json_data.get("platform") is not None else None,
    )
    device.comm = json_data.get("comm") or json_data.get("com")
    return device


def _sensor_from_config(json_data: dict, default_device_id: str | None = None) -> Sensor:
    return Sensor(
        observable_property=json_data.get("observable_property", "unknown"),
        procedure=json_data.get("procedure", "configured-measurement"),
        feature_of_interest=json_data.get("feature_of_interest", "unknown-feature"),
        sensor_id=json_data.get("sensor_id", "unknown"),
        device_id=json_data.get("device_id", default_device_id),
        unit=json_data.get("unit", None),
    )


class ManagerClient:
    def __init__(self, base_url: str, token: str = "", send_observation_path: str = "/newEvent", timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.send_observation_path = send_observation_path
        self.timeout_seconds = timeout_seconds

    def send_observation_ttl(self, ttl: str, reader_id: str, device_id: str) -> None:
        response = requests.post(
            f"{self.base_url}{self.send_observation_path}",
            json={
                "token": self.token,
                "eventType": "observation",
                "payloadFormat": "text/turtle",
                "payload": ttl,
                "deviceId": device_id,
                "readerId": reader_id,
            },
            headers={"Accept": "application/json, text/plain", "Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            raise RuntimeError(f"Error HTTP comunicando con Manager. Status={response.status_code}. Body={response.text}")

    def register_device(self, reader_id: str, device: Device) -> None:
        response = requests.post(
            f"{self.base_url}/registerDevice",
            json={
                "token": self.token,
                "schemaVersion": "phonendo.event.v1",
                "readerId": reader_id,
                "deviceId": device.device_id,
                "deviceType": device.device_type,
                "creationDatetime": int(time.time() * 1000),
            },
            headers={"Accept": "application/json, text/plain", "Content-Type": "application/json"},
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            raise RuntimeError(f"Error HTTP registrando device en Manager. Status={response.status_code}. Body={response.text}")


class ReaderCore:
    def __init__(
        self,
        reader_id: str | None = None,
        token: str | None = None,
        manager_url: str | None = None,
        config: Any | None = None,
        allow_new_devices: bool = True,
        allow_new_sensors: bool = True,
        manager_client: ManagerClient | None = None,
        **_ignored,
    ) -> None:
        self._core = _NativeReaderCore(reader_id or "", allow_new_devices, allow_new_sensors)
        self.reader_id = self._core.reader_id
        self.manager_client = manager_client or ManagerClient(manager_url or "", token or "")
        self.devices: dict[str, Device] = {}

    @property
    def last_error(self) -> str:
        return self._core.last_error

    def _raise_last_error(self) -> None:
        error = self.last_error
        if error.startswith("Ya existe") or "already exists" in error or "no puede estar vacío" in error:
            raise ValueError(error)
        raise RuntimeError(error)

    def add_device(self, device: Device) -> None:
        if not self._core.add_device(device):
            self._raise_last_error()
        self.devices[device.device_id] = device

    def register_device(self, device: Device) -> None:
        self.add_device(device)
        self.manager_client.register_device(self.reader_id, device)

    def get_device(self, device_id: str) -> Device | None:
        return self.devices.get(device_id)

    def load_devices_from_config(self, config: dict, default_device_id: str | None = None) -> None:
        for device_json in config.get("devices", []):
            self.register_device(_device_from_config(device_json, default_device_id=default_device_id or self.reader_id))

        for sensor_json in config.get("sensors", []):
            sensor = _sensor_from_config(sensor_json)
            device = self.devices.get(sensor.device_id)
            if device is None:
                continue
            if not self._core.add_sensor(device.device_id, sensor):
                self._raise_last_error()
            device.add_sensor(sensor)

    def handle_measurement_data(self, observation: Observation, send: bool = True) -> Observation | None:
        device_id = observation.device_id or self.reader_id
        sensor_id = observation.sensor_id or "unknown-sensor"
        had_device = device_id in self.devices

        ingested = self._core.handle_measurement_data(observation)
        if ingested is None:
            return None

        if device_id not in self.devices:
            self.devices[device_id] = Device(device_id, "device")
        if not self.devices[device_id].has_sensor(sensor_id):
            self.devices[device_id].add_sensor(
                Sensor(
                    observation.observable_property or "unknown",
                    observation.procedure or "unknown",
                    observation.feature_of_interest or "unknown",
                    sensor_id=sensor_id,
                    unit=observation.unit,
                    device_id=device_id,
                )
            )
        if not had_device:
            self.manager_client.register_device(self.reader_id, self.devices[device_id])
        if send:
            self.send_observation(ingested)
        return ingested

    def send_observation(self, observation: Observation) -> None:
        ttl = serialize_sosa_ttl(observation)
        self.manager_client.send_observation_ttl(ttl, self.reader_id, observation.device_id or "")
