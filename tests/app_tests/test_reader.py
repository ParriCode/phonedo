from __future__ import annotations

import json
import asyncio
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
READER_PATH = ROOT / "apps" / "reader"
sys.path.insert(0, str(READER_PATH))


fake_serial = types.ModuleType("serial")


class FakeSerialException(Exception):
    pass


class FakeSerial:
    def __init__(self, *args, **kwargs):
        pass

    def readline(self):
        return b""

    def close(self):
        pass


fake_serial.Serial = FakeSerial
fake_serial.SerialException = FakeSerialException
sys.modules.setdefault("serial", fake_serial)

fake_bleak = types.ModuleType("bleak")
fake_bleak.BleakScanner = object
sys.modules.setdefault("bleak", fake_bleak)

from linux.main import Reader, parse_args
from linux.communication.manager_client import ManagerClient
from reader_core.device import Device
from reader_core.core import ReaderCore
from reader_core.sensor import Sensor


@pytest.fixture(autouse=True)
def disable_manager_registration(monkeypatch):
    registered_devices = []

    def capture_register(self, reader_id, device):
        registered_devices.append((reader_id, device.device_id))

    monkeypatch.setattr(ManagerClient, "register_device", capture_register)
    return registered_devices


def write_reader_config(
    tmp_path: Path,
    *,
    device_id: str = "prueba2",
    sensor_id: str | None = "temp1",
    observable_property: str = "temperatura",
    procedure: str = "termorreceptor",
    feature_of_interest: str = "patient-001",
    unit: str | None = "CELSIUS",
    device_allow_conflicts: bool = False,
    sensor_allow_conflicts: bool = False,
    sensor_has_device_id: bool = True,
    malformed: bool = False,
    absolute_name: str = "devices_and_sensors.json",
) -> Path:
    config_path = tmp_path / absolute_name

    if malformed:
        config_path.write_text("{bad-json", encoding="utf-8")
        return config_path

    device = {
        "comm": "/dev/rfcomm1",
        "device_id": device_id,
        "allow_conflicts": device_allow_conflicts,
    }
    sensors = []

    if sensor_id is not None:
        sensor = {
            "sensor_id": sensor_id,
            "observable_property": observable_property,
            "procedure": procedure,
            "feature_of_interest": feature_of_interest,
            "allow_conflicts": sensor_allow_conflicts,
        }
        if sensor_has_device_id:
            sensor["device_id"] = device_id

        if unit is not None:
            sensor["unit"] = unit

        sensors.append(sensor)

    config = {
        "serial": {
            "baudrate": 9600,
        },
        "devices": [device],
        "sensors": sensors,
    }

    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def write_config_data(tmp_path: Path, config: dict) -> Path:
    config_path = tmp_path / "devices_and_sensors.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def build_reader(config_path: Path, **kwargs) -> Reader:
    return Reader(
        config_file=str(config_path),
        **kwargs,
    )


def capture_manager_send(reader: Reader) -> list[dict[str, str]]:
    sent_events = []

    def capture_send(ttl: str, reader_id: str, device_id: str) -> None:
        sent_events.append(
            {
                "ttl": ttl,
                "reader_id": reader_id,
                "device_id": device_id,
            }
        )

    reader.manager_client.send_observation_ttl = capture_send
    return sent_events


def parse_rfcomm(reader: Reader, raw: bytes, port: str = "/dev/rfcomm1"):
    observations = reader.serial_manager.parse_serial_message(port, raw)
    return observations[0] if observations else None


def send_rfcomm_to_reader(reader: Reader, raw: bytes, port: str = "/dev/rfcomm1"):
    sent_events = capture_manager_send(reader)
    observation = parse_rfcomm(reader, raw, port)
    assert observation is not None
    reader.handle_serial_data(observation)
    async def flush():
        while not reader.manager_output.queue.empty():
            await reader.manager_output.deliver_next()
    asyncio.run(flush())
    assert len(sent_events) == 1
    return sent_events[0]


def test_reader_processes_configured_json_value(tmp_path, capsys):
    # Descripción del test:
    # Simula un JSON mínimo recibido por RFCOMM y comprueba que el Reader usa la
    # configuración local para device, sensor, semántica, unidad y envío TTL.
    reader = build_reader(write_reader_config(tmp_path))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert event["device_id"] == "prueba2"
    assert "ph:prueba2 a sosa:Platform" in event["ttl"]
    assert "ph:temp1" in event["ttl"]
    assert "sosa:observes ph:temperatura" in event["ttl"]
    assert "sosa:usedProcedure ph:termorreceptor" in event["ttl"]
    assert "sosa:hasFeatureOfInterest ph:patient-001" in event["ttl"]
    assert "qudt:value 45.3" in event["ttl"]
    assert "qudt:hasUnit unit:CELSIUS" in event["ttl"]


def test_reader_processes_raw_configured_value(tmp_path):
    # Descripción del test:
    # Simula una línea cruda recibida por RFCOMM y comprueba que se usa como value.
    reader = build_reader(write_reader_config(tmp_path))

    event = send_rfcomm_to_reader(reader, b"83.4\n")

    assert event["device_id"] == "prueba2"
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "qudt:value 83.4" in event["ttl"]


def test_reader_processes_json_sensor_value(tmp_path):
    # Descripción del test:
    # Simula un JSON con sensor_id por RFCOMM y comprueba que el sensor
    # configurado genera una observación correcta.
    reader = build_reader(write_reader_config(tmp_path))

    event = send_rfcomm_to_reader(reader, b'{"sensor_id":"temp1","value":"45.3"}\n')

    assert event["device_id"] == "prueba2"
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "sosa:observes ph:temperatura" in event["ttl"]


def test_reader_processes_complete_json_rfcomm_message(tmp_path):
    # Descripción del test:
    # Simula un dispositivo Bluetooth que envía JSON completo por RFCOMM y
    # comprueba que el Reader respeta los campos recibidos.
    reader = build_reader(write_reader_config(tmp_path))
    raw = (
        b'{"device_id":"prueba2","sensor_id":"temp1","value":"45.3",'
        b'"observable_property":"temperatura","procedure":"termorreceptor",'
        b'"feature_of_interest":"patient-001","unit":"CELSIUS"}\n'
    )

    event = send_rfcomm_to_reader(reader, raw)

    assert "ph:prueba2 a sosa:Platform" in event["ttl"]
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "sosa:observedProperty ph:temperatura" in event["ttl"]
    assert "qudt:hasUnit unit:CELSIUS" in event["ttl"]


def test_json_value_without_configured_sensor_uses_fallback(tmp_path):
    # Descripción del test:
    # Configura un puerto con device pero sin sensor único y comprueba que un
    # JSON mínimo cae en sensor y semántica de fallback.
    reader = build_reader(write_reader_config(tmp_path, sensor_id=None))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert event["device_id"] == "prueba2"
    assert "sosa:madeBySensor ph:dev-rfcomm1" in event["ttl"]
    assert "sosa:observedProperty ph:unknown" in event["ttl"]
    assert "sosa:hasSimpleResult \"45.3\"" in event["ttl"]


def test_unknown_rfcomm_port_uses_reader_fallback_device(tmp_path):
    # Descripción del test:
    # Simula una lectura por un puerto no configurado y comprueba que el Reader
    # crea un device fallback y semántica unknown.
    reader = build_reader(write_reader_config(tmp_path))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n', port="/dev/rfcomm9")

    assert event["device_id"] == "reader"
    assert "sosa:madeBySensor ph:dev-rfcomm9" in event["ttl"]
    assert "sosa:observedProperty ph:unknown" in event["ttl"]


def test_portable_sensor_without_device_id_can_arrive_on_any_rfcomm_port(tmp_path):
    # Descripción del test:
    # Un sensor configurado sin device_id no queda ligado al puerto de ningún
    # device y se puede resolver por sensor_id aunque llegue por otro rfcomm.
    reader = build_reader(write_reader_config(tmp_path, sensor_has_device_id=False))

    event = send_rfcomm_to_reader(
        reader,
        b'{"sensor_id":"temp1","value":"45.3"}\n',
        port="/dev/rfcomm9",
    )

    assert event["device_id"] == "reader"
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "sosa:observedProperty ph:temperatura" in event["ttl"]


def test_single_portable_sensor_accepts_raw_value_on_any_rfcomm_port(tmp_path):
    # Descripción del test:
    # Si solo hay un sensor portable configurado, un valor crudo puede usar esa
    # configuración aunque el rfcomm asignado por el sistema cambie.
    reader = build_reader(write_reader_config(tmp_path, sensor_has_device_id=False))

    event = send_rfcomm_to_reader(reader, b"45.3\n", port="/dev/rfcomm9")

    assert event["device_id"] == "reader"
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "sosa:observedProperty ph:temperatura" in event["ttl"]


def test_sensor_with_device_id_is_rejected_on_wrong_rfcomm_port(tmp_path):
    # Descripción del test:
    # Un sensor con device_id queda ligado al puerto del device configurado; si
    # llega identificado por otro rfcomm, se descarta como conflicto de puerto.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm9",
        b'{"sensor_id":"temp1","value":"45.3"}\n',
    )

    assert observations == []


def test_device_id_conflict_is_discarded(tmp_path):
    # Descripción del test:
    # Envía un JSON con device_id distinto al configurado y comprueba que, sin
    # permitir conflictos, el parser descarta la medición.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"device_id":"otro","sensor_id":"temp1","value":"45.3"}\n',
    )

    assert observations == []


def test_sensor_id_conflict_is_discarded(tmp_path):
    # Descripción del test:
    # Envía un sensor distinto al configurado y comprueba que se descarta cuando
    # allow_conflicts es false.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"sensor_id":"temp2","value":"45.3"}\n',
    )

    assert observations == []


def test_observable_property_conflict_is_discarded(tmp_path):
    # Descripción del test:
    # Envía una propiedad observada distinta a la configurada y comprueba que la
    # medición no se acepta.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"sensor_id":"temp1","value":"45.3","observable_property":"presion"}\n',
    )

    assert observations == []


def test_procedure_conflict_is_discarded(tmp_path):
    # Descripción del test:
    # Envía un procedimiento distinto al configurado y comprueba que el parser
    # descarta el mensaje.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"sensor_id":"temp1","value":"45.3","procedure":"otro-procedimiento"}\n',
    )

    assert observations == []


def test_unit_conflict_is_discarded(tmp_path):
    # Descripción del test:
    # Envía una unidad distinta a la configurada y comprueba que se descarta la
    # medición.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"sensor_id":"temp1","value":"45.3","unit":"KELVIN"}\n',
    )

    assert observations == []


def test_device_conflict_can_be_allowed(tmp_path):
    # Descripción del test:
    # Permite conflictos de device y comprueba que un JSON con device_id nuevo se
    # acepta y se envía con ese nuevo device.
    reader = build_reader(write_reader_config(tmp_path, device_allow_conflicts=True))

    event = send_rfcomm_to_reader(
        reader,
        b'{"device_id":"otro","sensor_id":"temp1","value":"45.3"}\n',
    )

    assert event["device_id"] == "otro"
    assert "ph:otro a sosa:Platform" in event["ttl"]


def test_sensor_conflict_can_be_allowed(tmp_path):
    # Descripción del test:
    # Permite conflictos de sensor y comprueba que un sensor nuevo enviado en
    # JSON se acepta con su semántica propia.
    reader = build_reader(write_reader_config(tmp_path, sensor_allow_conflicts=True))
    raw = (
        b'{"device_id":"prueba2","sensor_id":"temp2","value":"45.3",'
        b'"observable_property":"presion","procedure":"barometro"}\n'
    )

    event = send_rfcomm_to_reader(reader, raw)

    assert "sosa:madeBySensor ph:temp2" in event["ttl"]
    assert "sosa:observedProperty ph:presion" in event["ttl"]
    assert "sosa:usedProcedure ph:barometro" in event["ttl"]


def test_new_allowed_sensor_without_metadata_does_not_inherit_old_semantics(tmp_path):
    # Descripción del test:
    # Permite sensores nuevos y comprueba que un JSON mínimo no hereda la semántica
    # de temp1 si no trae metadatos propios.
    reader = build_reader(write_reader_config(tmp_path, sensor_allow_conflicts=True))

    event = send_rfcomm_to_reader(reader, b'{"sensor_id":"temp2","value":"45.3"}\n')

    assert "sosa:madeBySensor ph:temp2" in event["ttl"]
    assert "sosa:observedProperty ph:unknown" in event["ttl"]
    assert "sosa:usedProcedure ph:unknown" in event["ttl"]


def test_new_allowed_sensor_with_json_uses_received_metadata(tmp_path):
    # Descripción del test:
    # Permite sensores nuevos y comprueba que un JSON completo para temp2 usa la
    # propiedad y procedimiento recibidos.
    reader = build_reader(write_reader_config(tmp_path, sensor_allow_conflicts=True))
    raw = (
        b'{"sensor_id":"temp2","value":"45.3",'
        b'"observable_property":"presion","procedure":"barometro"}\n'
    )

    event = send_rfcomm_to_reader(reader, raw)

    assert "sosa:madeBySensor ph:temp2" in event["ttl"]
    assert "sosa:observedProperty ph:presion" in event["ttl"]
    assert "sosa:usedProcedure ph:barometro" in event["ttl"]


def test_unit_generates_qudt_result(tmp_path):
    # Descripción del test:
    # Comprueba que una unidad configurada genera sosa:hasResult con QUDT en vez
    # de perder la unidad en hasSimpleResult.
    reader = build_reader(write_reader_config(tmp_path, unit="CELSIUS"))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert "@prefix qudt:" in event["ttl"]
    assert "sosa:hasResult [" in event["ttl"]
    assert "qudt:value 45.3" in event["ttl"]
    assert "qudt:hasUnit unit:CELSIUS" in event["ttl"]


def test_missing_unit_generates_simple_result(tmp_path):
    # Descripción del test:
    # Comprueba que cuando no hay unidad configurada se mantiene el resultado
    # simple SOSA.
    reader = build_reader(write_reader_config(tmp_path, unit=None))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert "@prefix qudt:" not in event["ttl"]
    assert "sosa:hasSimpleResult \"45.3\"" in event["ttl"]


def test_rdf_identifiers_use_ph_prefix_without_extra_resource_prefixes(tmp_path):
    # Descripción del test:
    # Comprueba que los identificadores RDF usan ph:valor y no prefijos
    # inventados como ph:device-valor o ph:sensor-valor.
    reader = build_reader(write_reader_config(tmp_path, unit=None))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert "ph:prueba2 a sosa:Platform" in event["ttl"]
    assert "sosa:madeBySensor ph:temp1" in event["ttl"]
    assert "ph:temperatura a sosa:ObservableProperty" in event["ttl"]
    assert "ph:device-" not in event["ttl"]
    assert "ph:sensor-" not in event["ttl"]
    assert "ph:property-" not in event["ttl"]


def test_help_does_not_start_reader(monkeypatch, capsys):
    # Descripción del test:
    # Ejecuta el parser con --help y comprueba que muestra la ayuda sin arrancar
    # el Reader.
    monkeypatch.setattr(sys, "argv", ["main.py", "--help"])

    with pytest.raises(SystemExit) as exc:
        parse_args()

    output = capsys.readouterr().out
    assert exc.value.code == 0
    assert "Qué hace:" in output
    assert "Configuración de conflictos:" in output
    assert "iniciando" not in output
    assert "Creando Reader" not in output


def test_relative_config_is_resolved_from_reader_folder():
    # Descripción del test:
    # Usa el nombre relativo devices_and_sensors.json y comprueba que el Reader
    # carga el fichero situado junto a main.py.
    reader = Reader(config_file="devices_and_sensors.json")

    assert reader.core.devices


def test_absolute_config_path_is_used(tmp_path):
    # Descripción del test:
    # Pasa una ruta absoluta temporal y comprueba que el Reader carga esa
    # configuración concreta.
    config_path = write_reader_config(tmp_path, device_id="device-absoluto")

    reader = build_reader(config_path)

    assert reader.core.get_device("device-absoluto") is not None


def test_malformed_config_raises_value_error(tmp_path):
    # Descripción del test:
    # Crea un JSON de configuración inválido y comprueba que el Reader informa
    # el error de carga.
    config_path = write_reader_config(tmp_path, malformed=True)

    with pytest.raises(ValueError):
        build_reader(config_path)


def test_reader_core_rejects_duplicate_device():
    # Descripción del test:
    # Añade dos veces el mismo device al core y comprueba que se rechaza el
    # duplicado.
    core = ReaderCore(reader_id="reader-test")
    device = Device("device-1", "device")

    core.add_device(device)

    with pytest.raises(ValueError):
        core.add_device(device)


def test_device_rejects_duplicate_sensor():
    # Descripción del test:
    # Añade dos veces el mismo sensor al mismo device y comprueba que se rechaza
    # el duplicado.
    device = Device("device-1", "device")
    sensor = Sensor("temperatura", "termorreceptor", "patient-001", sensor_id="temp1")

    device.add_sensor(sensor)

    with pytest.raises(ValueError):
        device.add_sensor(sensor)


def test_rfcomm_parser_ignores_empty_lines(tmp_path):
    # Descripción del test:
    # Envía una línea vacía al parser RFCOMM y comprueba que no genera
    # observaciones.
    reader = build_reader(write_reader_config(tmp_path))

    assert reader.serial_manager.parse_serial_message("/dev/rfcomm1", b"\n") == []


def test_rfcomm_parser_rejects_camel_case_json(tmp_path):
    # Descripción del test:
    # Envía JSON con claves camelCase y comprueba que el parser lo descarta.
    reader = build_reader(write_reader_config(tmp_path))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        (
            b'{"deviceId":"prueba2","sensorId":"temp1","value":"45.3",'
            b'"observableProperty":"temperatura","featureOfInterest":"patient-001"}\n'
        ),
    )

    assert observations == []


def test_rfcomm_parser_accepts_snake_case_json(tmp_path):
    # Descripción del test:
    # Envía JSON con claves snake_case y comprueba que el parser las interpreta.
    reader = build_reader(write_reader_config(tmp_path))

    observation = parse_rfcomm(
        reader,
        (
            b'{"device_id":"prueba2","sensor_id":"temp1","value":"45.3",'
            b'"observable_property":"temperatura","feature_of_interest":"patient-001"}\n'
        ),
    )

    assert observation.device_id == "prueba2"
    assert observation.sensor_id == "temp1"
    assert observation.observable_property == "temperatura"
    assert observation.feature_of_interest == "patient-001"


def test_manager_receives_configured_device_id(tmp_path):
    # Descripción del test:
    # Simula una medición por RFCOMM y comprueba que el Manager recibe el
    # device_id configurado.
    reader = build_reader(write_reader_config(tmp_path))

    event = send_rfcomm_to_reader(reader, b'{"value":"45.3"}\n')

    assert event["device_id"] == "prueba2"


def test_multiple_configured_sensors_same_device_are_selected_by_sensor_id(tmp_path):
    # Descripción del test:
    # Configura dos sensores en el mismo device y comprueba que cada mensaje
    # JSON se resuelve por sensor_id contra el sensor configurado correcto.
    config = {
        "serial": {"baudrate": 9600},
        "devices": [
            {
                "comm": "/dev/rfcomm1",
                "device_id": "pulsera-01",
                "allow_conflicts": False,
            }
        ],
        "sensors": [
            {
                "sensor_id": "temp1",
                "device_id": "pulsera-01",
                "observable_property": "temperatura",
                "procedure": "termorreceptor",
                "feature_of_interest": "patient-001",
                "unit": "CELSIUS",
            },
            {
                "sensor_id": "hr1",
                "device_id": "pulsera-01",
                "observable_property": "frecuencia-cardiaca",
                "procedure": "pulsometro",
                "feature_of_interest": "patient-001",
                "unit": "BPM",
            },
        ],
    }
    reader = build_reader(write_config_data(tmp_path, config))

    temp_event = send_rfcomm_to_reader(
        reader,
        (
            b'{"sensor_id":"temp1","value":"36.7",'
            b'"observable_property":"temperatura","procedure":"termorreceptor",'
            b'"feature_of_interest":"patient-001","unit":"CELSIUS"}\n'
        ),
    )
    hr_event = send_rfcomm_to_reader(
        reader,
        (
            b'{"sensor_id":"hr1","value":"80",'
            b'"observable_property":"frecuencia-cardiaca","procedure":"pulsometro",'
            b'"feature_of_interest":"patient-001","unit":"BPM"}\n'
        ),
    )

    assert "sosa:madeBySensor ph:temp1" in temp_event["ttl"]
    assert "sosa:observedProperty ph:temperatura" in temp_event["ttl"]
    assert "sosa:usedProcedure ph:termorreceptor" in temp_event["ttl"]
    assert "sosa:madeBySensor ph:hr1" in hr_event["ttl"]
    assert "sosa:observedProperty ph:frecuencia-cardiaca" in hr_event["ttl"]
    assert "sosa:usedProcedure ph:pulsometro" in hr_event["ttl"]


def test_adding_new_sensor_is_not_treated_as_conflict_when_reader_is_dynamic(tmp_path):
    # Descripción del test:
    # Diferencia conflicto de alta: si el Reader no está en modo static, un
    # sensor nuevo con metadatos completos se añade aunque no sea el sensor
    # configurado inicialmente.
    reader = build_reader(write_reader_config(tmp_path, sensor_allow_conflicts=True))

    event = send_rfcomm_to_reader(
        reader,
        (
            b'{"device_id":"prueba2","sensor_id":"temp2","value":"80",'
            b'"observable_property":"frecuencia-cardiaca",'
            b'"procedure":"pulsometro","feature_of_interest":"patient-001",'
            b'"unit":"BPM"}\n'
        ),
    )

    assert reader.core.get_device("prueba2").has_sensor("temp2")
    assert "sosa:madeBySensor ph:temp2" in event["ttl"]
    assert "sosa:observedProperty ph:frecuencia-cardiaca" in event["ttl"]


def test_static_device_rejects_new_sensor_even_if_conflicts_are_allowed(tmp_path):
    # Descripción del test:
    # Configura un device static y comprueba que no se puede añadir un sensor
    # nuevo aunque allow_conflicts permita aceptar datos distintos.
    config = {
        "serial": {"baudrate": 9600},
        "devices": [
            {
                "comm": "/dev/rfcomm1",
                "device_id": "prueba2",
                "allow_conflicts": True,
                "static": True,
            }
        ],
        "sensors": [
            {
                "sensor_id": "temp1",
                "device_id": "prueba2",
                "observable_property": "temperatura",
                "procedure": "termorreceptor",
                "allow_conflicts": True,
            }
        ],
    }
    reader = build_reader(write_config_data(tmp_path, config))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"device_id":"prueba2","sensor_id":"temp2","value":"80"}\n',
    )

    assert observations == []
    assert not reader.core.get_device("prueba2").has_sensor("temp2")


def test_static_reader_rejects_new_devices_even_if_conflicts_are_allowed(tmp_path):
    # Descripción del test:
    # Configura el Reader como static y comprueba que no descubre ni acepta un
    # device nuevo aunque el puerto permita conflictos.
    config = {
        "static": True,
        "serial": {"baudrate": 9600},
        "devices": [
            {
                "comm": "/dev/rfcomm1",
                "device_id": "prueba2",
                "allow_conflicts": True,
            }
        ],
        "sensors": [
            {
                "sensor_id": "temp1",
                "device_id": "prueba2",
                "observable_property": "temperatura",
                "procedure": "termorreceptor",
                "allow_conflicts": True,
            }
        ],
    }
    reader = build_reader(write_config_data(tmp_path, config))

    observations = reader.serial_manager.parse_serial_message(
        "/dev/rfcomm1",
        b'{"device_id":"otro-device","sensor_id":"temp1","value":"45.3"}\n',
    )

    assert observations == []
    assert reader.core.get_device("otro-device") is None


def test_parse_args_accepts_reader_identity_options(monkeypatch):
    # Descripción del test:
    # Comprueba que los argumentos de identidad del Reader se parsean
    # correctamente desde la CLI.
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--reader-id",
            "reader-1",
        ],
    )

    args = parse_args()

    assert args.reader_id == "reader-1"


def test_parse_args_accepts_config_path(monkeypatch):
    # Descripción del test:
    # Comprueba que el argumento --config se parsea y conserva la ruta indicada.
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "/tmp/reader-config.json"])

    args = parse_args()

    assert args.config == "/tmp/reader-config.json"
