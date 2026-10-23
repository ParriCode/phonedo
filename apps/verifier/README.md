# Verifier

`POST /verify` verifica un evento Captured y devuelve el resultado. Los eventos
verificados también se publican por `GET /stream` (SSE, evento `observation`).
Cada suscriptor recibe su copia; pueden conectarse varios Managers a la vez.
La autenticación del stream es `Authorization: Bearer <API_TOKEN_VERIFIER>`.

Para consumir eventos Captured de varios Managers, configura en el entorno:

```sh
VERIFIER_MANAGER_STREAMS='["http://manager-a:3003/stream/verifier", "http://manager-b:3003/stream/verifier"]'
```

Se usa `API_TOKEN_VERIFIER` para conectar. Los Managers deben habilitar
`stream.enabled` y `stream.verifiers`. Cada conexión tiene su trabajador y se
reconecta tras cinco segundos. Los rechazos se registran y no se publican como
Verified. Las observaciones verificadas se difunden a todos los suscriptores.
El cliente debe correlacionar `key` con sus propios eventos.

Estos streams no tienen historial ni confirmaciones. La autenticación actual
usa el mismo `MANAGER_PASSWORD` compartido: no hay claves independientes por
Manager. Los suscriptores autorizados pueden ver todos los resultados publicados.
