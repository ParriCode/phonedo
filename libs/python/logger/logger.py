from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class Logger:
    """
    Logger es una clase singleton que proporciona métodos para 
    registrar eventos en formato JSON, tanto en la consola como en 
    archivos. Permite configurar el nivel de verbosidad, si se deben 
    guardar los logs en archivos y si se deben mostrar los logs de desarrollo 
    (debug). Cada log incluye un timestamp, el nivel del log, en servicio que lo 
    genera, un mensaje y campos adicionales opcionales.
    """
    _instance: Optional["Logger"] = None

    def __init__(
        self,
        logs_dir: str | Path,
        service: str = "app",
        verbose: Optional[bool] = None,
        logging: Optional[bool] = None,
        dev: Optional[bool] = None,
    ) -> None:
        self.logs_dir = Path(logs_dir)
        self.service = service
        self.verbose = False if verbose is None else verbose #Por defecto, no mostrar logs en consola
        self.logging = True if logging is None else logging #Por defecto, guardar logs en archivos
        self.dev = False if dev is None else dev #Por defecto, no mostrar logs de desarrollo (debug)

        if self.logging:
            self.logs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def init(
        cls,
        logs_dir: str | Path,
        service: str = "app",
        verbose: Optional[bool] = None,
        logging: Optional[bool] = None,
        dev: Optional[bool] = None,
    ) -> "Logger":
        cls._instance = cls(
            logs_dir=logs_dir,
            service=service,
            verbose=verbose,
            logging=logging,
            dev=dev,
        )
        return cls._instance

    @classmethod
    def instance(cls) -> "Logger":
        if cls._instance is None:
            raise RuntimeError("Logger no inicializado. Llama a Logger.init(...) primero.")
        return cls._instance

    @classmethod
    def info(cls, message: str, *, dev: bool = False, **fields: Any) -> None:
        cls.instance()._write("INFO", message, dev=dev, fields=fields)

    @classmethod
    def warning(cls, message: str, *, dev: bool = False, **fields: Any) -> None:
        cls.instance()._write("WARNING", message, dev=dev, fields=fields)

    @classmethod
    def error(cls, message: str, *, dev: bool = False, **fields: Any) -> None:
        cls.instance()._write("ERROR", message, dev=dev, fields=fields)

    @classmethod
    def debug(cls, message: str, *, dev: bool = True, **fields: Any) -> None:
        cls.instance()._write("DEBUG", message, dev=dev, fields=fields)

    @classmethod
    def request(
        cls,
        method: str,
        path: str,
        status: int,
        *,
        dev: bool = False,
        **fields: Any,
    ) -> None:
        cls.instance()._write(
            "INFO",
            "request",
            dev=dev,
            fields={
                "method": method,
                "path": path,
                "status": status,
                **fields,
            },
        )

    def _write(self, level: str, message: str, *, dev: bool, fields: dict[str, Any]) -> None:
        if dev and not self.dev:
            return

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": self.service,
            "message": message,
            **fields,
        }

        line = json.dumps(record, ensure_ascii=False, default=str)
        
        # Mostrae en consola solo si verbose es true 
        if self.verbose:
            stream = sys.stderr if level in {"ERROR", "WARNING"} else sys.stdout
            print(line, file=stream, flush=True)
        # Guardar en archivo solo si logging es true
        if self.logging:
            target = self.logs_dir / f"{self.service}.log"
            with target.open("a", encoding="utf-8") as file:
                file.write(line + "\n")

  