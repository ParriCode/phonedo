# Diagramas de Phonendo

Actualizados: 23/10/2026. Basados en el Reader base Python, sin plataformas ni hardware específicos.

| Diagrama | Fuente | SVG | PNG |
| --- | --- | --- | --- |
| Reader: clases | [PlantUML](reader.plantuml) | [SVG](reader.svg) | [PNG](reader.png) |
| Phonendo: arquitectura | [PlantUML](phonendo.plantuml) | [SVG](phonendo.svg) | [PNG](phonendo.png) |
| Phonendo: secuencia completa | [PlantUML](phonendo-secuencia.plantuml) | [SVG](phonendo_secuencia.svg) | [PNG](phonendo_secuencia.png) |

El output HTTP al Manager no está implementado en el Reader base. El diagrama general lo marca como integración pendiente. La secuencia describe ese contrato de integración y separa la publicación futura: la llamada al Publisher sigue comentada y Stellar no está conectado.

Las opciones del Reader reflejan el código actual, incluido `ServerConfig.enabled`. Las respuestas HTTP del Manager no garantizan que la verificación haya finalizado correctamente.

Fuentes: `apps/reader/python/core/reader_core/`, `apps/reader/python/server/reader_server/`, `apps/manager/main.py`, `apps/storage/main.py`, `apps/storage/db.py`, `apps/verifier/main.py` y los requisitos objetivo de PHONENDO en el vault.

Renderizar con PlantUML (UTF-8), por ejemplo:

```sh
plantuml -charset UTF-8 -tsvg docs/*.plantuml
plantuml -charset UTF-8 -tpng docs/*.plantuml
```
