import os
import time
import asyncio
import threading
from pathlib import Path

import requests
from flask import Flask, request
from dotenv import load_dotenv
from bleak import BleakScanner, BleakClient

# Cargar config.env
load_dotenv(Path(__file__).resolve().parent.parent / "config.env")

EVENT_TYPE = {
    "Heartrate": "HEART_RATE"
}

discoverable_devices = []
listenable_peripherals = []
listening_peripherals = []


def promise_post_request(url, body):
    try:
        requests.post(url, json=body, timeout=5)
    except Exception as e:
        print(f"POST error to {url}: {e}")


app = Flask(__name__)


@app.get("/")
def healthcheck():
    return "Service is alive", 200

@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    device = data.get("device")
    serial_number = data.get("serialNumber")
    device_type = data.get("deviceType")

    if device:
        print("New device received: " + device)
        discoverable_devices.append(device)

        body = {
            "token": os.getenv("API_TOKEN_MANAGER"),
            "device": device,
            "type": device_type,
            "serialNumber": serial_number,
            "creationDatetime": int(time.time() * 1000)
        }

        promise_post_request(os.getenv("INTERNAL_URL_MANAGER_REGISTER_DEVICE"), body)
        return "Successfully registered", 200

    return "Bad request", 403


async def discover_callback(device, advertisement_data):
    is_discoverable = any(dev == device.address or dev == device.name for dev in discoverable_devices)

    if is_discoverable:
        listenable_peripherals.append(device)
        discoverable_devices[:] = [
            dev for dev in discoverable_devices
            if dev != device.address and dev != device.name
        ]
        print(f"Connected candidate peripheral: {device.address}")


async def init_bluetooth():
    scanner = BleakScanner(discover_callback)
    await scanner.start()
    print("Bluetooth scanning started")
    while True:
        await asyncio.sleep(1)


def parse_heart_rate(data: bytearray) -> int:
    if not data:
        return 0

    flags = data[0]
    hr_16bit = flags & 0x01

    if hr_16bit:
        return int.from_bytes(data[1:3], byteorder="little")
    return data[1]


async def listen_heart_rate_device(device):
    if device.address in listening_peripherals:
        return

    try:
        async with BleakClient(device.address) as client:
            print(f"Connected to peripheral: {device.address}")
            listening_peripherals.append(device.address)

            def notification_handler(sender, data):
                body = {
                    "token": os.getenv("API_TOKEN_MANAGER"),
                    "type": EVENT_TYPE["Heartrate"],
                    "value": parse_heart_rate(data),
                    "device": device.address,
                    "creationDatetime": int(time.time() * 1000)
                }
                promise_post_request(os.getenv("INTERNAL_URL_MANAGER_NEW_EVENT"), body)

            await client.start_notify("00002A37-0000-1000-8000-00805f9b34fb", notification_handler)

            while True:
                await asyncio.sleep(1)

    except Exception as e:
        print(f"Error listening to {device.address}: {e}")
    finally:
        if device.address in listening_peripherals:
            listening_peripherals.remove(device.address)


async def listen_heart_rate_events():
    while True:
        devices_to_listen = [
            device for device in listenable_peripherals
            if device.address not in listening_peripherals
        ]

        for device in devices_to_listen:
            asyncio.create_task(listen_heart_rate_device(device))

        await asyncio.sleep(3)


async def bluetooth_main():
    await asyncio.gather(
        init_bluetooth(),
        listen_heart_rate_events()
    )


def run_bluetooth_loop():
    asyncio.run(bluetooth_main())


if __name__ == "__main__":
    bluetooth_thread = threading.Thread(target=run_bluetooth_loop, daemon=True)
    bluetooth_thread.start()

    app.run(host="0.0.0.0", port=int(os.getenv("PORT_READER", 5000)))