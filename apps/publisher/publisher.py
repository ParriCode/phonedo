import atexit
import os
import queue
import secrets
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from publisher_support.batcher import SessionBatcher
from publisher_support.config import PublisherConfig
from publisher_support.logger import Logger
from publisher_support.prover import BatchNotMet, Prover
from publisher_support.signer import ManagerSigner
from publisher_support.stellar import ClaimFailed, StellarClaimer
from publisher_support.stream_client import StreamClient

load_dotenv(Path(__file__).resolve().parent / "config.env")


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


Logger.init(
    os.getenv("PHONENDO_LOGS_DIR", str(ROOT_DIR / "logs/services")),
    service="publisher",
    verbose=env_bool("PHONENDO_VERBOSE", False),
    logging=env_bool("PHONENDO_LOGGING", True),
    dev=env_bool("PHONENDO_DEV", False),
)

app = Flask(__name__)
publisher_config = PublisherConfig()
batcher = SessionBatcher(publisher_config.batch_size)
prover = Prover(publisher_config.circuits_path, publisher_config.policy)
claimer = StellarClaimer('',
                         publisher_config.stellar.get('source', ''),
                         publisher_config.stellar.get('network', 'testnet'))
signer = None
pending_batches = queue.Queue()
last_session_id = 0


def get_signer(batch):
    global signer
    if signer is not None:
        return signer
    return ManagerSigner(batch.get('managerUrl') or publisher_config.signer_manager,
                         batch.get('managerToken') or os.getenv('API_TOKEN_MANAGER', ''))


def next_session_id(started_at):
    """Identificador de sesión: inicio del lote en ms, único dentro del proceso."""
    global last_session_id
    last_session_id = max(int(started_at or time.time() * 1000), last_session_id + 1)
    return last_session_id


def process_batch(batch):
    """Prueba el lote, lo firma y cobra la sesión con claim()."""
    session_id = batch['sessionId']
    try:
        contract_id = publisher_config.contract_for(batch['verifierId'])
        if not contract_id:
            raise ValueError('No hay contrato configurado para este verifierId')
        commitment, proof_file = prover.prove(batch)
        signature = get_signer(batch).sign(batch, commitment, batch['patient'])
        target = StellarClaimer(contract_id, claimer.source, claimer.network)
        tx_hash = target.claim(batch, batch['patient'], commitment, signature, proof_file)
        Logger.info('publisher_session_paid', sessionId=session_id, deviceId=batch['deviceId'], verifierId=batch['verifierId'], contractId=contract_id, txHash=tx_hash)
        return tx_hash
    except BatchNotMet:
        Logger.info('publisher_session_not_met', sessionId=session_id, deviceId=batch['deviceId'])
    except Exception as error:  # un lote que falla no debe parar el worker de los siguientes
        Logger.error('publisher_session_failed', sessionId=session_id, deviceId=batch['deviceId'], verifierId=batch['verifierId'], error=str(error))
    return None


def worker():
    while True:
        batch = pending_batches.get()
        if batch is None:
            return
        process_batch(batch)


def consume_manager_event(message, manager_url=None, manager_token=None):
    batch = batcher.add(message, manager_url, manager_token)
    if not batch:
        return
    patient = publisher_config.patient_for(batch['deviceId'])
    if not patient:
        Logger.warning('publisher_patient_missing', deviceId=batch['deviceId'])
        return
    batch.update(sessionId=next_session_id(batch['startedAt']), salt=str(secrets.randbits(128)), patient=patient)
    Logger.info('publisher_batch_ready', sessionId=batch['sessionId'], deviceId=batch['deviceId'], managerId=batch['managerId'], verifierId=batch['verifierId'])
    pending_batches.put(batch)


@app.get("/")
def healthcheck():
    return "Service is alive", 200


@app.get("/info")
def info():
    return jsonify([
        {'peer': url.removesuffix('/stream'), 'transport': 'sse'}
        for url in sorted(manager_subscriptions.connected)
    ])


@app.get("/logs")
def logs():
    return jsonify(list(Logger.instance().messages))


threading.Thread(target=worker, daemon=True).start()
manager_targets = []
for target in publisher_config.manager_subscriptions:
    target = {'url': target} if isinstance(target, str) else dict(target)
    target['url'] = target['url'].rstrip('/') + '/stream'
    manager_targets.append(target)
manager_subscriptions = StreamClient(manager_targets, os.getenv('API_TOKEN_MANAGER', ''), consume_manager_event, with_source=True)
manager_subscriptions.start()
atexit.register(manager_subscriptions.close)


def start():
    Logger.info("service_starting", port=publisher_config.port)
    app.run(host=publisher_config.host, port=publisher_config.port)


if __name__ == "__main__":
    start()
