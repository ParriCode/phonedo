"""Ports implemented by platform adapters; observations stay as model objects."""
from typing import Protocol
from reader_core import Device, Observation


class ObservationOutput(Protocol):
    def register_device(self, reader_id: str, device: Device) -> None: ...
    def publish(self, reader_id: str, observation: Observation) -> None: ...


class Source(Protocol):
    async def start(self) -> None:
        """Acquire observations until cancelled."""
        ...

    async def stop(self) -> None:
        """Release resources, including after partial startup."""
        ...


class Server(Protocol):
    async def start(self) -> None:
        """Start listening and return."""
        ...

    async def stop(self) -> None: ...


class Worker(Protocol):
    async def run(self) -> None: ...
