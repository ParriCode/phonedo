import os
from pathlib import Path

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from db import PhonendoDB

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")

app = Flask(__name__)


my_db  = PhonendoDB()

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
        return "ok", 200

    except Exception as error:
        print(error)
        return "Internal server error", 500


@app.post("/event")
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

        return "ok", 200

    except Exception as error:
        print("[STORAGE /events] Error:", error)
        return "Internal server error", 500


@app.get("/raw")
def raw():
    try:
        data = my_db.read()
        return jsonify(data), 200
    except Exception as error:
        print(error)
        return "Internal server error", 500


def start():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_STORAGE", 5000)))


if __name__ == "__main__":
    start()