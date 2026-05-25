from pathlib import Path
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from device import Device
from serializer import SosaTTLSerializer
from sensors.temperature_sensor import TemperatureSensor
from core import ReaderCore

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



def main() -> None:
    #Primero cargar configuración
    env = load_env(Path(__file__).resolve().parent.parent / "config.env")

    manager_token = env.get("API_TOKEN_MANAGER", "token_manager")
    #Obtener la URL del manager
    register_device_url = env.get(
        "INTERNAL_URL_MANAGER_REGISTER_DEVICE",
        "http://localhost:3003/registerDevice",
    )
    #Obtener la URL del newEvent
    new_event_url = env.get(
        "INTERNAL_URL_MANAGER_NEW_EVENT",
        "http://localhost:3003/newEvent",
    )

    core = ReaderCore(
        token=manager_token,
        manager_url="http://localhost:3003",

    )

    temperature_sensor = TemperatureSensor(
        feature_of_interest="patient-001",
        interval_seconds=10,
        sensor_id="temp-001",
        procedure="temperature-measurement",
        unit="CELSIUS",
        min_value=30.0,
        max_value=45.0,
        raw_adapter=None,
    )

    patient_watch = Device(
        device_id="watch1",
        device_type="smart_watch",
        serial_number="1234",
        mac_address="0a:47:83:b5:be:84",
        platform="phonendo_research",
    )

    patient_watch.add_sensor(temperature_sensor)


    #core.add_device(patient_watch)

    observation = temperature_sensor.addObservation(34)

    core.register_device(patient_watch)    

    core.send_observation(observation)
    


if __name__ == "__main__":
    main()
