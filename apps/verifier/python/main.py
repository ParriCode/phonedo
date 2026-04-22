import os
import json
import time
from pathlib import Path

from flask import Flask, request
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
KEYS_PATH = BASE_DIR.parent / "keys.json"

with open(KEYS_PATH, "r", encoding="utf-8") as f:
    keys = json.load(f)

private_key = serialization.load_pem_private_key(
    keys["privateKey"].encode("utf-8"),
    password=None
)

app = Flask(__name__)


@app.get("/")
def healthcheck():
    return "Service is alive", 200


@app.post("/verify")
def verify():
    data = request.get_json(silent=True) or {}

    if not data.get("token") or data.get("token") != os.getenv("API_TOKEN_VERIFIER"):
        return "Not authorized", 401

    if not data.get("message"):
        return "Bad request", 403

    message = data["message"]

    message_bytes = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    signature = private_key.sign(
        message_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    ).hex()

    message["value"]["verifierSign"] = signature
    message["value"]["verifierSignDatetime"] = int(time.time() * 1000)

    print("Event Verified with signature:", signature)

    return message, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_VERIFIER", 5000)))