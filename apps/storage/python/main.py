import os
from pathlib import Path

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from db import init_db, write, get_all_items

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")

app = Flask(__name__)


@app.get("/")
def home():
    data = get_all_items()
    return jsonify(data), 200


@app.post("/devices")
def store_device():
    try:
        print("Device received:", request.json)

        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            return "Not authorized", 401

        if not request.json.get("message"):
            return "Bad request", 403

        message = request.json["message"]
        print("Registro en db:", message)

        write(message["key"], message["value"])

        print("Device registered on db:", message["key"])
        return "ok", 200

    except Exception as error:
        print(error)
        return "Internal server error", 500


@app.post("/events")
def store_event():
    try:
        print("[STORAGE /events] Body:", request.json)

        if not request.json.get("token") or request.json.get("token") != os.getenv("API_TOKEN_STORAGE"):
            return "Not authorized", 401

        if not request.json.get("message"):
            return "Bad request", 403

        message = request.json["message"]

        write(message["key"], message["value"])

        print("[STORAGE /events] Stored:", message["key"])

        return "ok", 200

    except Exception as error:
        print("[STORAGE /events] Error:", error)
        return "Internal server error", 500


@app.get("/raw")
def raw():
    try:
        data = get_all_items()
        return jsonify(data), 200
    except Exception as error:
        print(error)
        return "Internal server error", 500


def start():
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_STORAGE", 5000)))


if __name__ == "__main__":
    start()