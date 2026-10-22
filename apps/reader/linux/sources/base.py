"""Sources emit Observation objects through the supplied callback."""
from typing import Protocol


class Source(Protocol):
    async def start(self) -> None:
        """Acquire observations until stopped or cancelled."""
        ...

    async def stop(self) -> None:
        """Release resources; must also be safe after cancellation."""
        ...
