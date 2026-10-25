"""Reader service and optional HTTP/SSE server."""
from .service import ReaderService, ObservationOutput

from .manager_output import ManagerOutput

__all__ = ["ReaderService", "ObservationOutput", "ReaderServer", "ServerConfig", "ManagerOutput"]


def __getattr__(name):
    # The transport-independent facade must remain usable without aiohttp.
    if name in ('ReaderServer', 'ServerConfig'):
        from .server import ReaderServer, ServerConfig
        globals().update(ReaderServer=ReaderServer, ServerConfig=ServerConfig)
        return globals()[name]
    raise AttributeError(name)
