import json
import os
from pathlib import Path
from typing import Any

import plyvel


class PhonendoDB:
    DEVICE_PREFIX = "device:"
    EVENT_PREFIX = "event:"

    def __init__(self, path: str | None = None) -> None:
        self.db_path = path or os.getenv("PHONENDO_DB_PATH", "/tmp/phonendo_db_path")

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db = plyvel.DB(
            self.db_path,
            create_if_missing=True,
        )

        if self.db is None:
            raise RuntimeError("DB no inicializada")
    def write(self, key: str, value: dict) -> None:
        key_bytes = key.encode("utf-8")

#~        existing = self.db.get(key_bytes)
#~
#~        if existing is not None:
#~            raise KeyError(f"Key already exists: {key}")

        self.db.put(
            key_bytes,
            json.dumps(value, ensure_ascii=False).encode("utf-8")
        )

    def read(self, key : str ) -> dict | None:
        value = self.db.get(key.encode("utf-8"))
                
        if value  is None: 
            return None

        return json.loads(value.decode("utf-8"))

    def read_all(self) -> dict[str, dict[str, Any]]:
        """
        devuelve toda la base de datos
       
        """

        todo = {}

        for key_bytes, value_bytes in self.db.iterator():
            key = key_bytes.decode("utf-8")
            value = json.loads(value_bytes.decode('utf-8'))

            todo[key] = value 

        return todo 

    def close(self) -> None:
        if self.db is not None:
            self.db.close()

    def __enter__(self) -> "PhonendoDB":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
