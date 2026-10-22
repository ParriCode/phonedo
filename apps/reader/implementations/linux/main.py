"""Reader Linux mínimo con temperaturas simuladas y streaming HTTP."""
import asyncio
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

READER_DIR = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(READER_DIR / "python/core"), str(READER_DIR / "python/server")]

from reader_core import Observation, ReaderCore
from reader_server import ReaderServer, ServerConfig


async def main():
    core = ReaderCore(reader_id="reader-linux")
    server = ReaderServer(core, ServerConfig(enabled=True))
    try:
        await server.start()
        print("Temperaturas simuladas: http://127.0.0.1:3002/observations/stream")
        while True:
            core.ingest(Observation(
                device_id="simulated-device",
                sensor_id="simulated-temperature",
                observable_property="temperature",
                simple_result=round(random.uniform(20, 30), 2),
                unit="CELSIUS",
                phenomenon_time=datetime.now(timezone.utc),
                feature_of_interest="simulated-room",
                procedure="random-simulation",
            ))
            await asyncio.sleep(1)
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
