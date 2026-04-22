import json
import logging
from typing import Any, List, Tuple

import plyvel

db = plyvel.DB("/tmp/phonendo_db_final", create_if_missing=True)


def init_db():
    pass


def write(key: str, value: Any):
    try:
        existing = db.get(key.encode())
        if existing is None:
            db.put(key.encode(), json.dumps(value).encode())
    except Exception:
        db.put(key.encode(), json.dumps(value).encode())


def read(key: str):
    result = ""
    try:
        value = db.get(key.encode())
        if value is not None:
            result = json.loads(value.decode())
        else:
            logging.warning(f"DB {key} not found")
    except Exception:
        logging.warning(f"DB {key} not found")
    return result


def delete(key: str):
    try:
        db.delete(key.encode())
    except Exception:
        logging.warning(f"DB {key} not found")


def update(key: str, value: Any):
    delete(key)
    write(key, value)


def get_all_captured_items() -> List[Tuple[str, Any]]:
    captured_items = []

    try:
        for key, value in db:
            decoded_key = key.decode()
            decoded_value = json.loads(value.decode())

            if decoded_value.get("status") == "Captured":
                captured_items.append((decoded_key, decoded_value))

        return captured_items
    except Exception as err:
        logging.error(err)
        return captured_items


def get_all_items() -> List[Tuple[str, Any]]:
    items = []

    try:
        for key, value in db:
            decoded_key = key.decode()
            decoded_value = json.loads(value.decode())
            items.append((decoded_key, decoded_value))

        return items
    except Exception as err:
        logging.error(err)
        return items