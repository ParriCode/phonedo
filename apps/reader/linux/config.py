"""Configuration loading shared by the Linux runtime and source factory."""
from pathlib import Path
import json

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

        device_id = device_json.get("device_id", None)
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
