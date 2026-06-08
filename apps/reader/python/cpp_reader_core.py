from __future__ import annotations

import ctypes
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests


ROOT_DIR = Path(__file__).resolve().parents[3]
CPP_API = ROOT_DIR / "apps/reader/cpp/lib/PhonendoReader/python/reader_core_c_api.cpp"
CPP_SRC = ROOT_DIR / "apps/reader/cpp/lib/PhonendoReader/src"
BUILD_DIR = Path(__file__).resolve().parent / ".cpp_build"
LIB_PATH = BUILD_DIR / "libphonendo_reader_core.so"


def _build_library() -> None:
    BUILD_DIR.mkdir(exist_ok=True)
    sources = [
        CPP_API,
        CPP_SRC / "core.cpp",
        CPP_SRC / "device.cpp",
        CPP_SRC / "sensor.cpp",
        CPP_SRC / "obsevation.cpp",
        CPP_SRC / "serializer.cpp",
    ]
    if LIB_PATH.exists() and all(LIB_PATH.stat().st_mtime >= source.stat().st_mtime for source in sources):
        return
    subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            "-shared",
            "-fPIC",
            *[str(source) for source in sources],
            "-o",
            str(LIB_PATH),
        ],
        check=True,
    )


def _bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, datetime):
        return value.isoformat().encode()
    return str(value).encode()


def _text(ptr) -> str:
    if not ptr:
        return ""
    return ctypes.cast(ptr, ctypes.c_char_p).value.decode()


_build_library()
_lib = ctypes.CDLL(str(LIB_PATH))

_lib.prc_create.argtypes = [ctypes.c_char_p, ctypes.c_bool, ctypes.c_bool]
_lib.prc_create.restype = ctypes.c_void_p
_lib.prc_destroy.argtypes = [ctypes.c_void_p]
_lib.prc_last_error.argtypes = [ctypes.c_void_p]
_lib.prc_last_error.restype = ctypes.c_char_p
_lib.prc_free.argtypes = [ctypes.c_void_p]
_lib.prc_add_device.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
_lib.prc_add_device.restype = ctypes.c_bool
_lib.prc_add_sensor.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
]
_lib.prc_add_sensor.restype = ctypes.c_bool
_lib.prc_has_device.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_lib.prc_has_device.restype = ctypes.c_bool
_lib.prc_device_has_sensor.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
_lib.prc_device_has_sensor.restype = ctypes.c_bool
_lib.prc_device_count.argtypes = [ctypes.c_void_p]
_lib.prc_device_count.restype = ctypes.c_int
_lib.prc_handle_measurement.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_void_p),
]
_lib.prc_handle_measurement.restype = ctypes.c_bool
_lib.prc_serialize_sosa_ttl.argtypes = [
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_void_p),
]
_lib.prc_serialize_sosa_ttl.restype = ctypes.c_bool


@dataclass
class Observation:
    observable_property: str
    simple_result: Any
    phenomenon_time: datetime | str
    feature_of_interest: str
    procedure: str
    device_id: str | None = None
    sensor_id: str | None = None
    unit: str | None = None
    observation_id: str = field(default_factory=lambda: uuid4().hex)

    @staticmethod
    def from_cpp(data: dict) -> "Observation":
        return Observation(
            observable_property=data.get("observable_property", "unknown"),
            simple_result=data.get("simple_result", ""),
            phenomenon_time=data.get("phenomenon_time", ""),
            feature_of_interest=data.get("feature_of_interest", "unknown"),
            procedure=data.get("procedure", "unknown"),
            device_id=data.get("device_id") or None,
            sensor_id=data.get("sensor_id") or None,
            unit=data.get("unit") or None,
            observation_id=data.get("observation_id") or uuid4().hex,
        )

    def to_dict(self) -> dict:
        phenomenon_time = self.phenomenon_time
        if isinstance(phenomenon_time, datetime):
            phenomenon_time = phenomenon_time.isoformat()
        return {
            "observation_id": self.observation_id,
            "observable_property": self.observable_property,
            "simple_result": self.simple_result,
            "phenomenon_time": phenomenon_time,
            "feature_of_interest": self.feature_of_interest,
            "procedure": self.procedure,
            "unit": self.unit,
        }


class Sensor:
    def __init__(
        self,
        observable_property: str,
        procedure: str,
        feature_of_interest: str,
        sensor_id: str | None = None,
        unit: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self.sensor_id = sensor_id or str(uuid4())
        self.observable_property = observable_property
        self.procedure = procedure
        self.feature_of_interest = feature_of_interest
        self.unit = unit
        self.device_id = device_id

    @staticmethod
    def fromJson(json_data: dict, default_device_id: str | None = None) -> "Sensor":
        return Sensor(
            observable_property=json_data.get("observable_property", "unknown"),
            procedure=json_data.get("procedure", "configured-measurement"),
            feature_of_interest=json_data.get("feature_of_interest", "unknown-feature"),
            sensor_id=json_data.get("sensor_id", "unknown"),
            device_id=json_data.get("device_id", default_device_id),
            unit=json_data.get("unit", None),
        )


class Device:
    def __init__(self, device_id: str, device_type: str = "device", _legacy_address: str = "", platform: str | None = None, **_ignored_fields) -> None:
        if not device_id:
            raise ValueError("device_id no puede estar vacío")
        self.device_id = device_id
        self.device_type = device_type
        self.platform = platform
        self._sensors: dict[str, Sensor] = {}

    @staticmethod
    def fromJson(json_data: dict, default_device_id: str | None = None) -> "Device":
        device_id = json_data.get("device_id") or default_device_id
        device = Device(
            str(device_id),
            str(json_data.get("device_type") or json_data.get("deviceType") or "device"),
            platform=str(json_data["platform"]) if json_data.get("platform") is not None else None,
        )
        device.comm = json_data.get("comm") or json_data.get("com")
        return device

    def add_sensor(self, sensor: Sensor) -> None:
        if sensor.sensor_id in self._sensors:
            raise ValueError(f"Ya existe un sensor con id '{sensor.sensor_id}' en el dispositivo '{self.device_id}'")
        sensor.device_id = self.device_id
        self._sensors[sensor.sensor_id] = sensor

    def has_sensor(self, sensor_id: str) -> bool:
        return sensor_id in self._sensors

    def get_sensor(self, sensor_id: str) -> Sensor:
        return self._sensors[sensor_id]


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
        self.reader_id = reader_id or str(uuid4())
        self.manager_client = manager_client or ManagerClient(manager_url or "", token or "")
        self._ptr = _lib.prc_create(_bytes(self.reader_id), allow_new_devices, allow_new_sensors)
        if not self._ptr:
            raise RuntimeError("No se pudo crear ReaderCore C++")
        self.devices: dict[str, Device] = {}

    def __del__(self):
        ptr = getattr(self, "_ptr", None)
        if ptr:
            _lib.prc_destroy(ptr)
            self._ptr = None

    @property
    def last_error(self) -> str:
        return _lib.prc_last_error(self._ptr).decode()

    def _raise_last_error(self) -> None:
        error = self.last_error
        if error.startswith("Ya existe") or "already exists" in error or "no puede estar vacío" in error:
            raise ValueError(error)
        raise RuntimeError(error)

    def add_device(self, device: Device) -> None:
        ok = _lib.prc_add_device(self._ptr, _bytes(device.device_id), _bytes(device.device_type), _bytes(device.platform))
        if not ok:
            self._raise_last_error()
        self.devices[device.device_id] = device

    def register_device(self, device: Device) -> None:
        self.add_device(device)
        self.manager_client.register_device(self.reader_id, device)

    def get_device(self, device_id: str) -> Device | None:
        return self.devices.get(device_id)

    def load_devices_from_config(self, config: dict, default_device_id: str | None = None) -> None:
        for device_json in config.get("devices", []):
            self.register_device(Device.fromJson(device_json, default_device_id=default_device_id or self.reader_id))
        for sensor_json in config.get("sensors", []):
            sensor = Sensor.fromJson(sensor_json)
            device = self.devices.get(sensor.device_id)
            if device is None:
                continue
            ok = _lib.prc_add_sensor(
                self._ptr,
                _bytes(device.device_id),
                _bytes(sensor.sensor_id),
                _bytes(sensor.observable_property),
                _bytes(sensor.procedure),
                _bytes(sensor.feature_of_interest),
                _bytes(sensor.unit),
            )
            if not ok:
                self._raise_last_error()
            device.add_sensor(sensor)

    def handle_measurement_data(self, observation: Observation, send: bool = True) -> Observation | None:
        device_id = observation.device_id or self.reader_id
        sensor_id = observation.sensor_id or "unknown-sensor"
        had_device = device_id in self.devices
        out = ctypes.c_void_p()
        ok = _lib.prc_handle_measurement(
            self._ptr,
            _bytes(device_id),
            _bytes(sensor_id),
            _bytes(observation.observable_property),
            _bytes(observation.simple_result),
            _bytes(observation.phenomenon_time),
            _bytes(observation.feature_of_interest),
            _bytes(observation.procedure),
            _bytes(observation.unit),
            ctypes.byref(out),
        )
        if not ok:
            return None
        try:
            ingested = Observation.from_cpp(json.loads(_text(out)))
        finally:
            _lib.prc_free(out)

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
        out = ctypes.c_void_p()
        ok = _lib.prc_serialize_sosa_ttl(
            _bytes(observation.device_id),
            _bytes(observation.sensor_id),
            _bytes(observation.observable_property),
            _bytes(observation.simple_result),
            _bytes(observation.phenomenon_time),
            _bytes(observation.feature_of_interest),
            _bytes(observation.procedure),
            _bytes(observation.unit),
            _bytes(observation.observation_id),
            ctypes.byref(out),
        )
        if not ok:
            raise RuntimeError("No se pudo serializar Observation desde C++")
        try:
            ttl = _text(out)
        finally:
            _lib.prc_free(out)
        self.manager_client.send_observation_ttl(ttl, self.reader_id, observation.device_id or "")
