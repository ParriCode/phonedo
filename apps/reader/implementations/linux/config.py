"""Configuration loading shared by the Linux runtime and source factory."""
from pathlib import Path
import json
from reader_core import Device, Sensor

def config_bool(json_data: dict, key: str, default: bool) -> bool:
    value = json_data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "si", "sí"}
    return bool(value)


def load_config(path: Path) -> dict:
    """Load device, source and communication settings."""
    try:
        with path.open(encoding="utf-8") as file_:
            config = json.load(file_)
            if not isinstance(config, dict):
                raise ValueError("La configuración debe ser un objeto JSON")
            return config
    except FileNotFoundError: 
        #Sino existe el archivo y SE HA ESPECIFICADO , debe de mostrar error
        raise FileNotFoundError(f"No existe el archivo: {path}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Error al cargar el json: {error}")

def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
         

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def serial_config_from_config(config: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    serial_devices = {}
    serial_sensors = {}
    devices_by_id = {}
    reader_static = config_bool(config, "static", False)
    sensors_json = config.get("sensors", [])

    for device_json in config.get("devices", []):
        comm = device_json.get("comm") or device_json.get("com")
        if not comm:
            continue

        device_id = device_json.get("device_id") or config.get("default_device_id")
        metadata = {
            "port": comm,
            "device_id": device_id,
            "allow_conflicts": config_bool(device_json, "allow_conflicts", False),
            "static": config_bool(device_json, "static", False),
            "reader_static": reader_static,
        }

        serial_devices[comm] = metadata
        if device_id:
            devices_by_id[device_id] = metadata

    for sensor_json in sensors_json:
        sensor_id = sensor_json.get("sensor_id")
        if not sensor_id:
            continue

        device_id = sensor_json.get("device_id")
        device = devices_by_id.get(device_id, {})
        metadata = {
            "sensor_id": sensor_id,
            "observable_property": sensor_json.get("observable_property", "unknown"),
            "procedure": sensor_json.get("procedure", "configured-measurement"),
            "feature_of_interest": sensor_json.get("feature_of_interest", "unknown-feature"),
            "unit": sensor_json.get("unit", None),
            "sensor_allow_conflicts": config_bool(sensor_json, "allow_conflicts", False),
            "reader_static": reader_static,
        }

        if device_id:
            metadata.update(device_id=device_id, allow_conflicts=device.get("allow_conflicts", False), static=device.get("static", False), port=device.get("port"))
            if device and sum(1 for sensor in sensors_json if sensor.get("device_id") == device_id) == 1:
                device.update(metadata)

        serial_sensors[sensor_id] = metadata

    return serial_devices, serial_sensors


def device_from_config(
    json_data: dict,
    default_device_id: str | None = None,
) -> "Device":
    if not isinstance(json_data, dict):
        raise ValueError("La configuración de un device debe ser un objeto JSON")

    device_id = json_data.get("device_id") or default_device_id
    if not device_id:
        raise ValueError("device_id no puede estar vacío")

    device_type = json_data.get("device_type") or json_data.get("deviceType") or "device"
    platform = json_data.get("platform")

    device = Device(
        device_id=str(device_id),
        device_type=str(device_type),
        platform=str(platform) if platform is not None else None,
    )
    return device


def sensor_from_config(json_data: dict, default_device_id: str | None = None) -> "Sensor":
    if not isinstance(json_data, dict):
        raise ValueError("La configuración de un sensor debe ser un objeto JSON")

    return Sensor(
        observable_property=json_data.get("observable_property", "unknown"),
        procedure=json_data.get("procedure", "configured-measurement"),
        feature_of_interest=json_data.get("feature_of_interest", "unknown-feature"),
        sensor_id=json_data.get("sensor_id", "unknown"),
        device_id=json_data.get("device_id", default_device_id),
        unit=json_data.get("unit", None),
    )


def load_devices_from_config(core, config: dict, default_device_id: str | None = None) -> None:
    for device_json in config.get("devices", []):
        device = device_from_config(device_json, default_device_id=default_device_id)
        core.register_device(device)

    for sensor_json in config.get("sensors", []):
        sensor = sensor_from_config(sensor_json)
        device = core.get_device(sensor.device_id) if sensor.device_id else None
        if device is None:
            continue
        device.add_sensor(sensor)

