from pathlib import Path

from reader_core.core import ReaderCore
from reader_core.device import Device
from reader_core.sensor import Sensor

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
    core = ReaderCore(
        token=manager_token,
        manager_url="http://localhost:3003",

    )

    temperature_sensor = Sensor(
        observable_property="temperatura",
        procedure="temperature-measurement",
        feature_of_interest="patient-001",
        sensor_id="temp-001",
        unit="CELSIUS",
    )

    patient_watch = Device(
        device_id="watch1",
        device_type="smart_watch",
        mac_address="0a:47:83:b5:be:84",
        platform="phonendo_research",
    )

    patient_watch.add_sensor(temperature_sensor)


    #core.add_device(patient_watch)

    observation = temperature_sensor.build_observation(34)

    core.register_device(patient_watch)    

    core.send_observation(observation)
    


if __name__ == "__main__":
    main()
