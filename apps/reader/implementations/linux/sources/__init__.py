"""Build enabled sources without importing unused hardware dependencies."""
from logger import Logger
from ..config import config_bool, serial_config_from_config
from reader_server.contracts import Source

def bluetooth_manager_from_config(config: dict, on_measurement):

    bluetooth_json = config.get("bluetooth", {})
    ble_json = bluetooth_json.get("ble", {})

    if not config_bool(ble_json, "enabled", False):
        return None

    Logger.info("bluetooth_manager_configured")

    from .bluetooth import BluetoothSource

    return BluetoothSource(
        on_measurement=on_measurement,
        scan_timeout_seconds=ble_json.get("scan_timeout_seconds", 2.0),
        sleep_seconds=ble_json.get("sleep_seconds", 0.5),
    )

def serial_manager_from_config(config: dict, on_measurement):
    serial_json = config.get("serial", {})
    if not config_bool(serial_json, "enabled", True):
        return None
    if not serial_json and not any(
        device_json.get("comm") or device_json.get("com")
        for device_json in config.get("devices", [])
    ):
        return None

    serial_devices, serial_sensors = serial_config_from_config(config)
    serial_devices.update(serial_json.get("devices", {}))
    Logger.info(
        "serial_manager_configured",
        ports=serial_json.get("ports", None),
        devices=list(serial_devices.keys()),
        sensors=list(serial_sensors.keys()),
    )

    from .serial import SerialSource

    return SerialSource(
        on_measurement=on_measurement,
        port_glob=serial_json.get("glob", "/dev/rfcomm*"),
        ports=serial_json.get("ports", None),
        devices=serial_devices,
        sensors=serial_sensors,
        baudrate=serial_json.get("baudrate", 9600),
        read_timeout=serial_json.get("read_timeout", 1.0),
        poll_seconds=serial_json.get("poll_seconds", 1.0),
        reconnect_seconds=serial_json.get("reconnect_seconds", 2.0),
    )


def build_sources(config, on_measurement) -> list[Source]:
    # New source settings override their legacy top-level equivalents.
    settings = {**config, **config.get("sources", {})}
    sources = [source for source in (
        bluetooth_manager_from_config(settings, on_measurement),
        serial_manager_from_config(settings, on_measurement),
    ) if source is not None]
    local = settings.get("local_metrics", {})
    if config_bool(local, "enabled", False):
        from .local_metrics import LocalMetricsSource
        sources.append(LocalMetricsSource(
            on_measurement, interval_seconds=local.get("interval_seconds", 2),
            device_id=local.get("device_id", "local_pc"),
        ))
    return sources
