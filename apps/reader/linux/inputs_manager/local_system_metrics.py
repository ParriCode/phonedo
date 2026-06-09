import asyncio
import psutil
from datetime import datetime, timezone

class SystemMetricsManager:
    def __init__(self, on_measurement, interval_seconds=2):
        self.on_measurement = on_measurement
        self.interval_seconds = interval_seconds
        self.running = False

    async def start(self):
        self.running = True

        while self.running:
            now = datetime.now(timezone.utc)

            await self.emit("cpu_usage", psutil.cpu_percent(interval=None), "%", now)
            await self.emit("ram_usage", psutil.virtual_memory().percent, "%", now)
            await self.emit("disk_usage", psutil.disk_usage("/").percent, "%", now)

            temps = psutil.sensors_temperatures()

            for chip, entries in temps.items():
                for entry in entries:
                    label = entry.label or chip
                    sensor_id = f"temp_{chip}_{label}".replace(" ", "_").lower()
                    await self.emit(sensor_id, entry.current, "CELSIUS", now)

            await asyncio.sleep(self.interval_seconds)

    async def emit(self, sensor_id, value, unit, timestamp):
        obs = {
            "device_id": "local_pc",
            "sensor_id": sensor_id,
            "value": value,
            "unit": unit,
            "timestamp": timestamp.isoformat(),
            "observable_property": sensor_id,
            "procedure": "linux-system-read",
            "feature_of_interest": "host-system",
        }

        result = self.on_measurement(obs)

        if asyncio.iscoroutine(result):
            await result

    async def stop(self):
        self.running = False