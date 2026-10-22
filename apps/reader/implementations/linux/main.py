"""Linux command-line entry point; paths are configured only at startup."""
import argparse
import asyncio
import sys
from pathlib import Path

READER_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = READER_DIR.parents[1]
for path in (ROOT_DIR / "libs", READER_DIR, READER_DIR / "core/python", READER_DIR / "server/python"):
    sys.path.insert(0, str(path))

from implementations.linux.application import LinuxReader

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phonendo Python Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Qué hace:
  - Carga dispositivos y sensores desde devices_and_sensors.json.
  - Escucha puertos serie configurados, incluidos RFCOMM expuestos como /dev/rfcomm*.
  - Acepta mensajes serie en JSON, sensor:valor o valor plano.
  - Completa valores planos con la configuración del puerto y del sensor.
  - Convierte cada medición en una observación JSON.
  - Publica por stream y/o envía al Manager según communication.

Configuración de conflictos:
  - En devices[] y sensors[] se puede poner "allow_conflicts": true o false.
  - Si es false y un mensaje contradice la configuración, la medición se descarta.
  - Si es true, el dato recibido puede crear/usar el nuevo device o sensor recibido.

Ejemplos:
  python3 main.py
  python3 main.py --config devices_and_sensors.json
  python3 main.py --reader-id reader-1
""",
    )
    parser.add_argument("--reader-id", dest="reader_id", default=None, help="Identificador lógico del Reader. Por defecto usa reader_id del JSON o 'reader'.")
    parser.add_argument("--config", default="devices_and_sensors.json", help="Ruta al JSON de configuración de dispositivos, sensores y comunicaciones.")
    parser.add_argument("--verbose", action="store_true", default=None, help="Habilitar salida detallada para depuración.")
    parser.add_argument("--static", action="store_true", help="No descubrir dispositivos o sensores fuera de la configuración.")
    return parser.parse_args()



if __name__ == "__main__":

    args = parse_args()
    reader = LinuxReader(
        id=args.reader_id,
        config_file=args.config,
        verbose=args.verbose,
        static=args.static
    )
    asyncio.run(reader.run())
