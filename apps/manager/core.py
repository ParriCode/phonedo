"""Manager event processing and volatile retry queue."""
import threading
import time
import uuid
import requests
from logger import Logger
from pending_events import PendingEvents
from client import DeviceNotRegisteredError, InternalPostError
from event_auth import sign_event

class EventRejected(RuntimeError):
    pass

def get_message_from_response(response):
    if isinstance(response, dict) and isinstance(response.get("message"), dict):
        return response["message"]

    return response

class ManagerCore:
    def __init__(self, client, server, queue_size, retry_interval):
        self.client = client
        self.server = server
        self.http_readers = set()
        self.reader_source_lock = threading.Lock()
        self.reader_locks = {}
        self.pending_events = PendingEvents(queue_size, retry_interval,
                                           self.retry_event, self.queue_discarded)

    def prefer_http(self, reader_id):
        with self.lock_for_reader(reader_id):
            self.http_readers.add(reader_id)

    def close(self):
        self.pending_events.close()

    def lock_for_reader(self, reader_id):
        with self.reader_source_lock:
            return self.reader_locks.setdefault(reader_id, threading.Lock())

    def submit_observation(self, body):
        device_id = body["deviceId"]
        reader_id = body["readerId"]
        payload = body["payload"]
        payload_format = body["payloadFormat"]
        event_type = body["eventType"]

        Logger.info("event_received", deviceId=device_id, readerId=reader_id, eventType=event_type)
        Logger.debug("event_payload_received", deviceId=device_id, readerId=reader_id, payload=payload)
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
        job = {"message": message, "stage": "lookup", "verified": None}
        return self.attempt_event(job, enqueue=True)

    def on_reader_stream_event(self, body):
        if not isinstance(body, dict) or any(not body.get(field) for field in (
                "readerId", "deviceId", "payload", "payloadFormat", "eventType")):
            Logger.warning("reader_stream_invalid_event")
            return
        reader_id = body["readerId"]
        with self.lock_for_reader(reader_id):
            if reader_id in self.http_readers:
                Logger.debug("reader_stream_ignored_http_priority", readerId=reader_id)
                return
            self.submit_observation(body)

    def process_event(self, job):
        """Keep Captured in memory; persist only a positively verified event."""
        message = job["message"]
        if job["stage"] == "lookup":
            self.client.get_device(message["value"]["deviceId"])
            job["stage"] = "signing"
        if job["stage"] == "signing":
            message["value"]["managerHash"] = sign_event(message)
            job["stage"] = "verification"
        if job["stage"] == "verification":
            self.server.publish_captured(message)
            response = self.client.verify_event(message)
            if isinstance(response, dict) and response.get("verified") is False:
                raise EventRejected("Verifier rejected event")
            verified = get_message_from_response(response)
            if (not isinstance(response, dict) or response.get("verified") is not True
                    or not isinstance(verified, dict)
                    or verified.get("key") != message["key"]
                    or not isinstance(verified.get("value"), dict)
                    or verified["value"].get("status") != "Verified"
                    or not verified["value"].get("verifierSign")):
                raise RuntimeError("Invalid verification response")
            job["verified"] = verified
            job["stage"] = "store_verified"
        self.server.publish_verified(job["verified"])
        stored = self.client.store_event(job["verified"])
        if get_message_from_response(stored) != job["verified"]:
            raise RuntimeError("Storage did not confirm the verified message")
        Logger.info("event_stored_as_verified", eventId=message["key"])

    def attempt_event(self, job, *, enqueue):
        event_id = job["message"]["key"]
        try:
            self.process_event(job)
            return {"eventId": event_id, "status": "Verified"}, 200
        except requests.Timeout:
            if enqueue:
                self.pending_events.put(job)
            Logger.warning("event_pending_timeout", eventId=event_id, stage=job["stage"])
            return {"eventId": event_id, "status": "Pending", "stage": job["stage"]}, 202
        except Exception as error:
            rejected = isinstance(error, EventRejected) or (
                job["stage"] == "verification" and isinstance(error, InternalPostError)
                and error.status in (400, 422))
            status = 422 if rejected else (404 if isinstance(error, DeviceNotRegisteredError)
                                         else 500 if job["stage"] == "signing" else 502)
            Logger.warning("event_discarded" if rejected else "event_processing_failed",
                           eventId=event_id, stage=job["stage"], error=str(error))
            return {"eventId": event_id, "status": "Rejected" if rejected else "Failed",
                    "stage": job["stage"]}, status

    def retry_event(self, job):
        _, status = self.attempt_event(job, enqueue=False)
        return status == 202

    def queue_discarded(self, job):
        Logger.warning("event_discarded_queue_full", eventId=job["message"]["key"],
                       stage=job["stage"])

