"""Reader Linux mínimo con lecturas simuladas (temperatura o pulso) y streaming HTTP."""
import asyncio
import random
import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

READER_DIR = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(READER_DIR / "python/core"), str(READER_DIR / "python/server")]

from reader_core import Observation, ReaderCore
from reader_server import ReaderServer, ServerConfig, ManagerOutput


TEMPERATURE = {"deviceId": "simulated-device", "sensorId": "simulated-temperature", "property": "temperature",
               "unit": "CELSIUS", "min": 20, "max": 30, "featureOfInterest": "simulated-room",
               "intervalSeconds": 1}
PULSE = {"deviceId": "simulated-pulse-band", "sensorId": "simulated-pulse", "property": "heart_rate",
         "unit": "BPM", "min": 95, "max": 120, "featureOfInterest": "simulated-patient",
         "intervalSeconds": 1}
COLD_CHAIN = {"deviceId": "simulated-cold-chain", "sensorId": "simulated-cold-chain-temperature", "property": "temperature",
              "unit": "CELSIUS", "min": 2, "max": 8, "featureOfInterest": "simulated-transport",
              "intervalSeconds": 1}


def simulation_settings(settings):
    """Bloque `simulation` del config: `"pulse"`, `"temperature"`, `"coldchain"` o un objeto que sobrescribe campos."""
    simulation = settings.get('simulation', 'temperature')
    if isinstance(simulation, str):
        return dict({"temperature": TEMPERATURE, "pulse": PULSE, "coldchain": COLD_CHAIN}[simulation])
    return {**TEMPERATURE, **simulation}


async def main():
    config_path = Path(os.getenv('READER_CONFIG_PATH', str(READER_DIR / 'config.json')))
    settings = json.loads(config_path.read_text()) if config_path.exists() else {}
    core = ReaderCore(reader_id=settings.get('readerId', 'reader-linux'))
    simulation = simulation_settings(settings)
    server_settings = dict(settings.get('server', {'enabled': True}))
    server_settings['stream_enabled'] = settings.get('stream', {}).get('enabled', True)
    server_config = ServerConfig(**server_settings)
    output = ManagerOutput.from_config(config_path) if config_path.exists() else ManagerOutput([])
    server = (ReaderServer(core, server_config, outputs=(output,))
              if output.managers else ReaderServer(core, server_config))
    try:
        await server.start()
        print(f"Lecturas simuladas ({simulation['property']}): http://127.0.0.1:3002/stream")
        while True:
            core.ingest(Observation(
                device_id=simulation["deviceId"],
                sensor_id=simulation["sensorId"],
                observable_property=simulation["property"],
                simple_result=round(random.uniform(simulation["min"], simulation["max"]), 2),
                unit=simulation["unit"],
                phenomenon_time=datetime.now(timezone.utc),
                feature_of_interest=simulation["featureOfInterest"],
                procedure="random-simulation",
            ))
            await asyncio.sleep(simulation["intervalSeconds"])
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
