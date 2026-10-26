#!/usr/bin/env python3
"""Siembra la pila de ejemplo a través del panel, igual que haría un operador desde la web.

Por qué existe: ./phonendo no debe conocer los detalles de cada servicio. Las definiciones
viven como datos en deploy/demo/ejemplo.json y este script solo las envía a la API del panel
(POST /api/local/containers). Es idempotente: un servicio que ya existe se respeta
(y si estaba parado, se arranca); solo se crean los que faltan.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CABECERAS = {'X-Phonendo-Control': 'local', 'Content-Type': 'application/json'}


def llamar(base, ruta, cuerpo=None, metodo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(base + ruta, data=datos, headers=CABECERAS,
                                      method=metodo or ('POST' if datos is not None else 'GET'))
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            return json.load(respuesta)
    except urllib.error.HTTPError as error:
        detalle = error.read().decode(errors='replace')[:300]
        raise SystemExit(f'El panel rechazó {ruta}: {detalle}')


def esperar(base, operacion, limite=1200):
    for _ in range(limite):
        estado = llamar(base, '/api/local/operations/' + operacion['id'])
        if estado['state'] == 'succeeded':
            return estado
        if estado['state'] == 'failed':
            raise SystemExit('Falló la operación: ' + estado.get('error', 'sin detalle'))
        time.sleep(1)
    raise SystemExit('La operación tardó demasiado')


def sembrar(base, definicion):
    carpeta = definicion.parent
    existentes = {item['id']: item for item in llamar(base, '/api/local/containers')}
    for servicio in json.loads(definicion.read_text())['servicios']:
        servicio = dict(servicio)
        identificador = servicio['id']
        if identificador in existentes:
            if existentes[identificador]['state'] != 'running':
                print(f'  {servicio["name"]}: ya existe, arrancando', flush=True)
                esperar(base, llamar(base, '/api/local/containers/' + identificador, {'action': 'start'}))
            else:
                print(f'  {servicio["name"]}: ya existe', flush=True)
            continue
        servicio['config'] = json.loads((carpeta / servicio.pop('configFile')).read_text())
        servicio.setdefault('port', 0)
        print(f'  {servicio["name"]}: creando (la primera vez compila la imagen)', flush=True)
        esperar(base, llamar(base, '/api/local/containers', servicio))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Uso: sembrar.py http://127.0.0.1:8080 deploy/demo/ejemplo.json')
    sembrar(sys.argv[1].rstrip('/'), Path(sys.argv[2]).resolve())
