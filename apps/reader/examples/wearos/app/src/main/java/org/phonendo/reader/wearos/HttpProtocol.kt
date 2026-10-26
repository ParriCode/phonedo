// Parte pura del servidor HTTP del reloj: leer la cabecera de la petición,
// decidir la ruta, comprobar el Bearer y montar las respuestas.
//
// Está separada de los sockets para probarla en la JVM. Reproduce el contrato
// del ejemplo ESP32 (reader_http.cpp) y del Reader Python (server.py): solo
// GET; /devices/{id} con un único segmento; cualquier otra cosa es 404 con
// {"error":"not_found"}; la autorización se comprueba antes de enrutar y
// compara "Bearer <token>" entero en tiempo constante.
package org.phonendo.reader.wearos

import java.io.ByteArrayOutputStream
import java.security.MessageDigest

data class HttpRequest(val method: String, val path: String, private val headers: Map<String, String>) {
    fun header(name: String): String? = headers[name.lowercase()]
}

sealed interface Route {
    data object Health : Route
    data object Metadata : Route
    data object Devices : Route
    data class Device(val id: String) : Route
    data object Stream : Route
    data object NotFound : Route
}

object HttpProtocol {
    const val SSE_HEAD = "HTTP/1.1 200 OK\r\n" +
        "Content-Type: text/event-stream\r\n" +
        "Cache-Control: no-cache\r\n" +
        "X-Accel-Buffering: no\r\n" +
        "Connection: keep-alive\r\n\r\n"

    const val HEALTH_OK = "{\"status\":\"ok\"}"
    const val UNAUTHORIZED = "{\"error\":\"unauthorized\"}"
    const val NOT_FOUND = "{\"error\":\"not_found\"}"
    const val TOO_MANY_SUBSCRIBERS = "{\"error\":\"too_many_subscribers\"}"
    const val STREAM_UNAVAILABLE = "{\"error\":\"stream_unavailable\"}"
    const val BAD_REQUEST = "{\"error\":\"bad_request\"}"
    const val INTERNAL_ERROR = "{\"error\":\"internal_error\"}"

    private const val DEVICES_PREFIX = "/devices/"

    /** Primera línea y cabeceras, sin la línea vacía final; null si no es HTTP. */
    fun parseHead(lines: List<String>): HttpRequest? {
        val parts = lines.firstOrNull()?.split(' ') ?: return null
        if (parts.size != 3 || !parts[2].startsWith("HTTP/") || !parts[1].startsWith("/")) return null
        val headers = HashMap<String, String>()
        for (line in lines.drop(1)) {
            val colon = line.indexOf(':')
            if (colon <= 0) continue
            headers[line.substring(0, colon).trim().lowercase()] = line.substring(colon + 1).trim()
        }
        return HttpRequest(parts[0], parts[1].substringBefore('?'), headers)
    }

    fun route(method: String, path: String): Route {
        if (method != "GET") return Route.NotFound
        return when (path) {
            "/health" -> Route.Health
            "/metadata" -> Route.Metadata
            "/devices" -> Route.Devices
            "/stream" -> Route.Stream
            else -> deviceRoute(path)
        }
    }

    private fun deviceRoute(path: String): Route {
        if (!path.startsWith(DEVICES_PREFIX)) return Route.NotFound
        val raw = path.substring(DEVICES_PREFIX.length)
        if (raw.isEmpty() || raw.contains('/')) return Route.NotFound
        val id = percentDecode(raw) ?: return Route.NotFound
        return Route.Device(id)
    }

    /** Decodifica %XX como UTF-8; null si la secuencia está mal formada. */
    fun percentDecode(value: String): String? {
        val out = ByteArrayOutputStream()
        var i = 0
        while (i < value.length) {
            val c = value[i]
            if (c == '%') {
                if (i + 3 > value.length) return null
                val byte = value.substring(i + 1, i + 3).toIntOrNull(16) ?: return null
                out.write(byte)
                i += 3
            } else {
                out.write(c.toString().toByteArray(Charsets.UTF_8))
                i++
            }
        }
        return String(out.toByteArray(), Charsets.UTF_8)
    }

    /** Sin token configurado no se pide nada, como en Python y el ESP32. */
    fun isAuthorized(token: String, authorization: String?): Boolean {
        if (token.isEmpty()) return true
        val expected = "Bearer $token".toByteArray(Charsets.UTF_8)
        val received = (authorization ?: "").toByteArray(Charsets.UTF_8)
        return MessageDigest.isEqual(expected, received)
    }

    fun deviceNotFound(deviceId: String): String =
        "{\"error\":\"device_not_found\",\"deviceId\":${jsonString(deviceId)}}"

    fun jsonResponse(status: Int, body: String): ByteArray {
        val bytes = body.toByteArray(Charsets.UTF_8)
        val head = "HTTP/1.1 $status ${reason(status)}\r\n" +
            "Content-Type: application/json\r\n" +
            "Content-Length: ${bytes.size}\r\n" +
            "Connection: close\r\n\r\n"
        return head.toByteArray(Charsets.UTF_8) + bytes
    }

    private fun reason(status: Int): String = when (status) {
        200 -> "OK"
        400 -> "Bad Request"
        401 -> "Unauthorized"
        404 -> "Not Found"
        503 -> "Service Unavailable"
        else -> "Internal Server Error"
    }

    /** Cadena JSON entre comillas, con el mismo escape que serialization.cpp. */
    fun jsonString(value: String): String {
        val out = StringBuilder(value.length + 2).append('"')
        for (c in value) {
            when (c) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> if (c < ' ') out.append(String.format("\\u%04x", c.code)) else out.append(c)
            }
        }
        return out.append('"').toString()
    }
}
