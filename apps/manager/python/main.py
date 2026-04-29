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

#campos del newEvent
"""

    "token": self.token,
                "eventType": "observation",
                "payloadFormat": "text/turtle",
                "payload": ttl,
                "deviceId": device_id,
                "readerId": reader_id
"""
#Campo para el registro de un nuevo dispositivo (y reader)


#Se guarda el reader que realizó el registro , aunque loq ue realmente importa es el deviceId
"""

                "token": self.token,
                "readerId": reader_id,
                "deviceId": device.device_id,
                "deviceType":device.device_type,
                "serialNumber": device.serial_number,
                "creationDatetime": int(time.time() * 1000),
"""

#registrar dispositivol
@app.post("/registerDevice")
def register_device():
    #Obtener cuerpo del mensaje
    body = request.get_json(silent=True) or {}
    #Es necesario el TOKEN para el manager
    if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
        return "Not authorized", 401


    #Obtener campos del cuerpo json
    device_id           = body.get("deviceId")
    reader_id           = body.get("readerId")
    device_type         = body.get("deviceType")
    serial_number       = body.get("serialNumber")
    mac_address         = body.get("macAddress")
    creation_date_time  = body.get("creationDatetime")
    
    #verificar que todos los cuerpos existen
    if not device_id:
        return {"error": "deviceId is required"}, 400

    if not reader_id:
        return {"error": "readerId is required"}, 400

    if not device_type:
        return {"error": "deviceType is required"}, 400

    if not serial_number:
        return {"error": "serialNumber is required"}, 400
    
    if not mac_address:
        return {"error": "macAddress is required"}, 400
    
    if not creation_date_time:
        return {"error": "creation_date_time is requires"}, 400 
    


    print(f"New device received: {device_id}")

    message = {
        "key": device_id,
        "value": {
            "deviceId": device_id,
            "deviceType": device_type,
            "serialNumber": serial_number,
            "macAddress":mac_address,
            "registeredByReader": reader_id,
            "registrationDatetime": int(time.time() * 1000),
        },
    }

    #Registro de un nuevo token
    storage_body = {
        "token": os.getenv("API_TOKEN_STORAGE"),
        "message":message
    }
    #meter en el stotage
    response = post_request(os.getenv("INTERNAL_URL_STORAGE_DEVICES"), storage_body)

    print("respuesta al post = ", response)

    return "Successfully registered", 200

    return "Bad request", 403

#registrar evento
@app.post("/newEvent")
def new_event():
    body = request.get_json(silent=True) or {}

    if not body.get("token") or body.get("token") != os.getenv("API_TOKEN_MANAGER"):
        return "Not authorized", 401


    device_id           = body.get("deviceId")
    reader_id           = body.get("readerId")
    payload             = body.get("payload")
    payload_format      = body.get("payloadFormat")
    event_type          = body.get("eventType")


    if not device_id:
        return {"error": "deviceId is required"}, 400

    if not reader_id:
        return {"error": "readerId is required"}, 400

    if not payload:
        return {"error": "payload is required"}, 400

    if not payload_format:
        return {"error": "payloadFormat is required"}, 400
    
    if not event_type:
        return {"error": "eventType is required"}, 400
    

    print(f"New event received: {device_id} // {reader_id} // {payload}")
    #construccion del mensaje
    message = {
        "key": str(uuid.uuid4()),
        "value": {
            "schemaVersion": "phonendo.event.v1",
            "eventType": "observation",
            "readerId": reader_id,
            "deviceId": device_id,
            "payloadFormat": payload_format,
            "payload": payload,
            "status": "Captured",
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