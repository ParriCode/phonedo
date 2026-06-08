from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STORAGE_PATH = ROOT / "apps" / "storage"
STORAGE_SITE_PACKAGES = (
    STORAGE_PATH
    / ".venv"
    / "lib"
    / f"python{sys.version_info.major}.{sys.version_info.minor}"
    / "site-packages"
)


def load_storage(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PHONENDO_DB_PATH", str(tmp_path / "storage.leveldb"))
    monkeypatch.setenv("API_TOKEN_STORAGE", "token_storage")
    monkeypatch.setenv("PHONENDO_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("PHONENDO_VERBOSE", "false")
    monkeypatch.setenv("PHONENDO_LOGGING", "true")
    monkeypatch.setenv("PHONENDO_DEV", "true")

    if STORAGE_SITE_PACKAGES.exists():
        sys.path.insert(0, str(STORAGE_SITE_PACKAGES))
    sys.path.insert(0, str(STORAGE_PATH))
    sys.modules.pop("db", None)

    spec = importlib.util.spec_from_file_location(
        "storage_main_under_test",
        STORAGE_PATH / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_storage_register_device_accepts_message_payload(tmp_path, monkeypatch):
    storage = load_storage(tmp_path, monkeypatch)
    try:
        response = storage.app.test_client().post(
            "/registerDevice",
            json={
                "token": "token_storage",
                "message": {
                    "key": "prueba1",
                    "value": {
                        "deviceId": "prueba1",
                        "deviceType": "device",
                        "registeredByReader": "reader",
                        "registrationDatetime": 1780589929568,
                        "managerHash": "113319ff543e41f0bb84c60da92d425231e990da7c70ac215d35cd9153577fad",
                    },
                },
            },
        )

        assert response.status_code == 200
        assert storage.my_db.read("prueba1")["deviceId"] == "prueba1"
    finally:
        storage.my_db.close()
