# Publisher

Servicio previsto para la publicación de los datos verificados de Phonendo.
Su integración en el flujo actual está pendiente: el Manager termina tras guardar
el evento Verified en Storage.

Publisher no se arranca con `tools/dev.sh` ni participa en las pruebas de
integración actuales. `config.json` mantiene el servicio deshabilitado y listas de Managers y Storages
para su futura integración.

[Arquitectura general](../../docs/diagramas.md).
