"""
author: Jose Luis Parrilla Fuentes jlpf0006@red.ujaen.es

file: reader.py

reader has de responsabily of catch sensors información and send them to the manager , also if a sensor is not register, this can check and notg register twice
"""
import os
import time
import asyncio
import threading
from pathlib import Path


from abc import ABC , abstractmethod
import requests
from flask import Flask, request
from dotenv import load_dotenv
from bleak import BleakScanner, BleakClient
from enum import Enum 

from uuid import uuid4

from dataclasses import dataclass , field 


from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

from datetime import datetime , timezone

from typing import Optional , List
class Sensor(Enum):
    EXAMPLE = "example"


class ObservableProperty(Enum):
    HEART_RATE = "HeartRate"
    TEMPERATURE = "Temperature"
    SPO2 = "SpO2"



SOSA = Namespace("http://www.w3.org/ns/sosa/")
TIME = Namespace("http://www.w3.org/2006/time#")
EX = Namespace("https://example.org/phonendo#")

@dataclass
class Observation:
    """
    Representa una sosa:Observation.
    """
    observable_property: ObservableProperty
    platafform: Optional[str] 
    simple_result: int | float | str
    feature_of_interest: str
    phenomenon_time: Optional[datetime] = None
    procedure: Optional[str] = None
    observation_id: str = field(default_factory=lambda: f"obs_{uuid4().hex}")

    def to_graph(self, graph: Graph, sensor_uri: URIRef) -> URIRef:
        obs_uri = EX[self.observation_id]
        graph.add((obs_uri, RDF.type, SOSA.Observation))
        graph.add((obs_uri, SOSA.madeBySensor, sensor_uri))
        graph.add((obs_uri, SOSA.observedProperty, EX[self.observable_property.value]))
        graph.add((obs_uri, SOSA.hasFeatureOfInterest, EX[self.feature_of_interest]))

        # hasSimpleResult
        if isinstance(self.simple_result, int):
            result_literal = Literal(self.simple_result, datatype=XSD.integer)
        elif isinstance(self.simple_result, float):
            result_literal = Literal(self.simple_result, datatype=XSD.decimal)
        else:
            result_literal = Literal(self.simple_result)

        graph.add((obs_uri, SOSA.hasSimpleResult, result_literal))

        # resultTime
        graph.add((
            obs_uri,
            SOSA.resultTime,
            #tipo de dato xsd::dateTime
        ))

        # phenomenonTime opcional
        if self.phenomenon_time is not None:
            graph.add((
                obs_uri,
                SOSA.phenomenonTime,
                Literal(self.phenomenon_time.isoformat(), datatype=XSD.dateTime)
            ))

        # usedProcedure opcional
        if self.procedure:
            graph.add((obs_uri, SOSA.usedProcedure, EX[self.procedure]))

        return obs_uri

class SensorBase(ABC):
    """
    Clase base abstracta para cualquier sensor modelado con SOSA.
    """

    def __init__(
        self,
        sensor_id: str,
        observable_property: ObservableProperty,
        feature_of_interest: str,
        platform: Optional[str] = None,
    ) -> None:
        self.sensor_id = sensor_id
        self.observable_property = observable_property
        self.feature_of_interest = feature_of_interest
        self.platform = platform
        self.observations: List[Observation] = []

    def add_observation(
        self,
        simple_result: int | float | str,
        result_time: Optional[datetime] = None,
        phenomenon_time: Optional[datetime] = None,
        procedure: Optional[str] = None,
    ) -> Observation:
        """
        Añade una medición nueva al sensor.
        """
        if result_time is None:
            result_time = datetime.now(timezone.utc)

        obs = Observation(
            observable_property=self.observable_property,
            simple_result=simple_result,
            result_time=result_time,
            phenomenon_time=phenomenon_time,
            feature_of_interest=self.feature_of_interest,
            procedure=procedure,
        )
        self.observations.append(obs)
        return obs

    def to_graph(self) -> Graph:
        """
        Convierte el sensor y todas sus observaciones a un grafo RDF.
        """
        graph = Graph()
        graph.bind("sosa", SOSA)
        graph.bind("time", TIME)
        graph.bind("ex", EX)

        sensor_uri = EX[self.sensor_id]

        # El sensor
        graph.add((sensor_uri, RDF.type, SOSA.Sensor))
        graph.add((sensor_uri, SOSA.observes, EX[self.observable_property.value]))

        # ObservableProperty
        graph.add((EX[self.observable_property.value], RDF.type, SOSA.ObservableProperty))

        # FeatureOfInterest
        graph.add((EX[self.feature_of_interest], RDF.type, SOSA.FeatureOfInterest))

        # Platform opcional
        if self.platform:
            platform_uri = EX[self.platform]
            graph.add((platform_uri, RDF.type, SOSA.Platform))
            graph.add((platform_uri, SOSA.hosts, sensor_uri))

        # Observaciones
        for observation in self.observations:
            observation.to_graph(graph, sensor_uri)

        return graph

    def to_ttl(self) -> str:
        """
        Devuelve el Turtle listo para enviar por HTTP.
        """
        return self.to_graph().serialize(format="turtle")

    @abstractmethod
    def sensor_kind(self) -> str:
        """
        Método abstracto para que cada sensor concreto se describa.
        """
        raise NotImplementedError



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