import os
from pathlib import Path

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from db import PhonendoDB

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")

app = Flask(__name__)


my_db  = PhonendoDB()


def storage_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    return (
        request.headers.get("X-Storage-Token")
        or request.headers.get("token")
        or request.headers.get("Token")
    )

@app.get("/")
def home():
    data = my_db.read_all()
    return jsonify(data), 200


@app.post("/registerDevice")
def store_device():
    try:
        print("Device received:", request.json)
        #checkear el token
        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            return "Not authorized", 401

        if not request.json.get("message"):
            return "Bad request", 403
        #Obtener el mensaje
        message = request.json["message"]
        print("Registro en db:", message)

        my_db.write(message["key"], message["value"])

        print("Device registered on db:", message["key"])
        return jsonify(message), 200

    except Exception as error:
        print(error)
        return "Internal server error", 500


@app.get("/devices/<device_id>")
def get_device(device_id):
    try:

        print("[DEBUG /device] device_id:", device_id, flush=True)

        token = storage_token_from_request()

        if not token or token != os.getenv("API_TOKEN_STORAGE"):
            return jsonify({"error": "Not authorized"}), 401

        device = my_db.read(device_id)

        print("[DEBUG /device] device_id:", device, flush=True)


        if not device:
            return jsonify({"error": "Device not found"}), 404

        return jsonify({
            "key": device_id,
            "value": device
        }), 200

    except Exception as error:
        print("[STORAGE /device] Error:", error)
        return jsonify({"error": "Internal server error"}), 500


@app.post("/events")
def store_event():
    try:
        print("[STORAGE /events] Body:", request.json)

        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            return "Not authorized", 401

        if not request.json.get("message"):
            return "Bad request", 403

        message = request.json["message"]

        my_db.write(message["key"], message["value"])

        print("[STORAGE /events] Stored:", message["key"])

        return jsonify(message), 200

    except Exception as error:
        print("[STORAGE /events] Error:", error)
        return "Internal server error", 500


@app.get("/raw")
def raw():
    try:
        data = my_db.read_all()
        return jsonify(data), 200
    except Exception as error:
        print(error)
        return "Internal server error", 500


def start():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_STORAGE", 5000)))


if __name__ == "__main__":
    start()
