from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
READER_PATH = ROOT / "apps" / "reader" / "python"
sys.path.insert(0, str(READER_PATH))


fake_bleak = types.ModuleType("bleak")
fake_bleak.BleakScanner = object


class FakeBleakClient:
    instances = []

    def __init__(self, mac, disconnected_callback=None):
        self.mac = mac
        self.disconnected_callback = disconnected_callback
        self.is_connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        FakeBleakClient.instances.append(self)

    async def connect(self):
        self.connect_calls += 1
        self.is_connected = True

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False


fake_bleak.BleakClient = FakeBleakClient
sys.modules["bleak"] = fake_bleak

import bluetooth_manager


def test_discover_macs_simulated(monkeypatch):
    async def fake_scan(self):
        return {
            "AA:BB:CC:DD:EE:FF": (None, None),
            "11:22:33:44:55:66": (None, None),
        }

    monkeypatch.setattr(
        bluetooth_manager.BluetoothDeviceManager,
        "scan",
        fake_scan,
    )

    manager = bluetooth_manager.BluetoothDeviceManager()

    macs = asyncio.run(manager.discover_macs())

    assert macs == [
        "aa:bb:cc:dd:ee:ff",
        "11:22:33:44:55:66",
    ]


def test_connect_macs_and_save_devices():
    async def scenario():
        FakeBleakClient.instances = []
        manager = bluetooth_manager.BluetoothDeviceManager()

        await manager.connect_and_register("AA:BB:CC:DD:EE:FF")

        assert "aa:bb:cc:dd:ee:ff" in manager.devices
        assert manager.devices["aa:bb:cc:dd:ee:ff"].mac == "aa:bb:cc:dd:ee:ff"
        assert len(FakeBleakClient.instances) == 1
        assert FakeBleakClient.instances[0].mac == "aa:bb:cc:dd:ee:ff"
        assert FakeBleakClient.instances[0].connect_calls == 1
        assert FakeBleakClient.instances[0].is_connected is True

        await manager.stop()

    asyncio.run(scenario())
