# Diagramas de Phonendo

Actualizados: 23/10/2026. Basados en el Reader base Python, sin plataformas ni hardware específicos.

| Diagrama | Fuente | SVG | PNG |
| --- | --- | --- | --- |
| Reader: clases | [PlantUML](reader.plantuml) | [SVG](reader.svg) | [PNG](reader.png) |
| Phonendo: arquitectura | [PlantUML](phonendo.plantuml) | [SVG](phonendo.svg) | [PNG](phonendo.png) |
| Phonendo: secuencia simplificada | [PlantUML](phonendo-secuencia.plantuml) | [SVG](phonendo_secuencia.svg) | [PNG](phonendo_secuencia.png) |

Los generales muestran únicamente Reader, Manager, Verifier, Storage y Publisher.
El UML interno del Reader se conserva. Los diagramas internos de los demás servicios
quedan para una revisión posterior.

El flujo operativo usa SSE desde el Reader y HTTP para verificar y guardar Verified.
El Verifier también consume el SSE de Managers y publica resultados para varios
suscriptores; el Manager aún no consume esos resultados para continuar el guardado.
Las conexiones pendientes están anotadas, incluida la publicación futura.

Fuentes actuales: `apps/reader/python/server/reader_server/server.py`,
`apps/manager/{manager,core,server,client}.py`, `apps/verifier/verifier.py`,
`apps/storage/main.py`, las utilidades locales en `apps/manager/manager_support/` y `apps/verifier/verifier_support/` y
`tests/integration/test_pipeline.py`.

Fuentes históricas conservadas: `apps/reader/python/core/reader_core/`,
`apps/reader/python/server/reader_server/`, `apps/manager/main.py`,
`apps/storage/db.py`, `apps/verifier/main.py` y los requisitos objetivo de PHONENDO
explicaban la versión anterior; las rutas antiguas del Manager y Verifier han cambiado.

Renderizar con PlantUML (UTF-8), por ejemplo:

```sh
plantuml -charset UTF-8 -tsvg docs/*.plantuml
plantuml -charset UTF-8 -tpng docs/*.plantuml
```
