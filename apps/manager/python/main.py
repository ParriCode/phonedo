from pathlib import Path
import os
import uuid
import hashlib
import time

import requests
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv(Path(__file__).resolve().parent.parent / "config.env")

app = Flask(__name__)


def post_request(url, body):
    response = requests.post(url, json=body, timeout=10)
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return response.text


def to_bytes(string):
    return list(string.encode("utf-8"))


def sign_data_source(message):
    hash_value = hashlib.sha256(
        (message["value"]["device"] + "Phonendo").encode("utf-8")
    ).hexdigest()

    bytes_value = to_bytes(hash_value)
    return message



#ok 
@app.get("/")
def alive():
    return "Service is alive"

#registrar dispositivol
@app.post("/registerDevice")
def register_device():
    
    body = request.get_json(silent=True) or {}

    if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
        return "Not authorized", 401

    device = body.get("device")
    type_ = body.get("type")
    serial_number = body.get("serialNumber")
    creation_datetime = body.get("creationDatetime")

    if device:
        print("New device received: " + str(device))

        message = {
            "key": device,
            "value": {
                "device": device,
                "type": type_,
                "serialNumber": serial_number,
                "creationDatetime": creation_datetime,
            },
        }

        storage_body = {
            "token": os.getenv("API_TOKEN_STORAGE"),
            "message": message,
        }

        post_request(os.getenv("INTERNAL_URL_STORAGE_DEVICES"), storage_body)

        return "Successfully registered", 200

    return "Bad request", 403

#registrar evento
@app.post("/newEvent")
def new_event():
    body = request.get_json(silent=True) or {}

    if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
        return "Not authorized", 401

    type_ = body.get("type")
    value = body.get("value")
    device = body.get("device")

    print(f"New event received: {type_} // {value} // {device}")

    message = {
        "key": str(uuid.uuid4()),
        "value": {
            "type": type_,
            "value": value,
            "device": device,
            "creationDatetime": int(time.time() * 1000),
        },
    }

    message = sign_data_source(message)

    try:
        request_body = {
            "token": os.getenv("API_TOKEN_STORAGE"),
            "message": message,
        }

        stored_message = post_request(
            os.getenv("INTERNAL_URL_STORAGE_EVENTS"),
            request_body,
        )

        request_body["message"] = stored_message
        request_body["token"] = os.getenv("API_TOKEN_VERIFIER")

        verified_message = post_request(
            os.getenv("INTERNAL_URL_VERIFIER_VERIFY"),
            request_body,
        )

        request_body["message"] = verified_message
        request_body["token"] = os.getenv("API_TOKEN_STORAGE")

        stored_verified_message = post_request(
            os.getenv("INTERNAL_URL_STORAGE_EVENTS"),
            request_body,
        )

        request_body["message"] = stored_verified_message
        request_body["token"] = os.getenv("API_TOKEN_PUBLISHER")

        # published_message = post_request(
        #     os.getenv("INTERNAL_URL_PUBLISHER_PUBLISH"),
        #     request_body,
        # )

        request_body["token"] = os.getenv("API_TOKEN_STORAGE")

        # delete_request(
        #     os.getenv("INTERNAL_URL_STORAGE_EVENTS") + "/" + published_message["key"],
        #     request_body,
        # )

    except Exception as error:
        print("Error processing event:", error)

    return "Event accepted", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT_MANAGER", "3003")))