# Phonendo

Phonendo es una plataforma de servicios para recoger datos de dispositivos y sensores,
coordinar su procesamiento, verificar su integridad y almacenarlos. La publicación
de los datos forma parte del diseño y está pendiente de integración.

## Servicios

| Servicio | Responsabilidad |
| --- | --- |
| **Reader** | Recoge observaciones y las expone mediante un stream SSE. |
| **Manager** | Coordina el flujo, calcula el hash del contenido del evento y gestiona los reintentos por timeout. |
| **Verifier** | Valida el evento, comprueba el hash y firma el resultado verificado. |
| **Storage** | Guarda los dispositivos registrados y los eventos verificados. |
| **Publisher** | Se encargará de publicar los datos. Su integración está pendiente. |

## Arquitectura general

![Relaciones entre los servicios de Phonendo](docs/phonendo.svg)

El Manager consume las observaciones del Reader por SSE. Si un mismo Reader envía
eventos por `/newEvent`, esa entrada HTTP tiene prioridad sobre su stream.
La verificación y el guardado del flujo completo actual se realizan mediante HTTP.
El Verifier también consume streams de Managers y publica resultados por SSE;
el Manager todavía no utiliza esos resultados SSE para continuar el guardado.

## Secuencia general

![Secuencia simplificada entre los servicios de Phonendo](docs/phonendo_secuencia.svg)

Solo se guarda el evento tras una verificación positiva. Un rechazo explícito lo
descarta; un timeout lo deja en una cola temporal en memoria para reintentarlo.
Publisher aparece como una fase futura.

## Ejecución local

Requisitos: Python 3.11 o superior, soporte para entornos virtuales y `pip`.

Configura `deploy/env/dev.env` con las URLs, los puertos y los secretos de los
servicios. Después genera sus configuraciones y arranca el entorno:

```sh
./tools/generate_configs.sh
./tools/dev.sh
```

El generador escribe los archivos `config.env` de los servicios. El Reader del
entorno local utiliza el ejemplo Linux con observaciones simuladas.

## Pruebas

Prepara el entorno de pruebas:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tests/requirements.txt
```

Ejecuta las pruebas de los componentes y la integración con servicios reales:

```sh
./tools/test.sh
./tools/test_integration.sh
```

Las pruebas del Reader en C++ requieren un compilador con soporte C++17. La prueba
de integración utiliza puertos y una base de datos temporales, comprueba streams,
firmas e integridad del dato almacenado y cierra los servicios al terminar.

## Documentación y referencia

- [Reader](apps/reader/README.md), [Manager](apps/manager/README.md),
  [Verifier](apps/verifier/README.md), [Storage](apps/storage/README.md) y
  [Publisher](apps/publisher/README.md).
- [Diagramas y fuentes PlantUML editables](docs/diagramas.md).
- Moya, F., Quesada, F. J., Martínez, L. et al. *Phonendo: a platform for publishing wearable data on distributed ledger technologies*. Wireless Networks (2023). [Publicación original](https://doi.org/10.1007/s11276-023-03458-7).

Licencia [MIT](LICENSE.txt).
