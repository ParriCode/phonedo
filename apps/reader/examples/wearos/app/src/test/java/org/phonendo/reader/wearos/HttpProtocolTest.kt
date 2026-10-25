// Contrato HTTP del servidor del reloj, el mismo que el del ESP32 y el Reader
// Python: rutas GET, 404 con cuerpo JSON, Bearer exacto y respuestas que
// cierran la conexión.
package org.phonendo.reader.wearos

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HttpProtocolTest {
    @Test
    fun parsesRequestLineAndHeaders() {
        val request = HttpProtocol.parseHead(
            listOf("GET /devices?x=1 HTTP/1.1", "Host: reloj:8080", "authorization: Bearer abc")
        )!!
        assertEquals("GET", request.method)
        assertEquals("/devices", request.path)
        assertEquals("Bearer abc", request.header("Authorization"))
        assertEquals("reloj:8080", request.header("host"))
        assertNull(request.header("X-Nada"))
    }

    @Test
    fun rejectsMalformedRequestLine() {
        assertNull(HttpProtocol.parseHead(listOf("BASURA")))
        assertNull(HttpProtocol.parseHead(listOf("GET health HTTP/1.1")))
        assertNull(HttpProtocol.parseHead(emptyList()))
    }

    @Test
    fun routesReaderEndpoints() {
        assertEquals(Route.Health, HttpProtocol.route("GET", "/health"))
        assertEquals(Route.Metadata, HttpProtocol.route("GET", "/metadata"))
        assertEquals(Route.Devices, HttpProtocol.route("GET", "/devices"))
        assertEquals(Route.Stream, HttpProtocol.route("GET", "/stream"))
        assertEquals(Route.Device("oneplus-watch-3"), HttpProtocol.route("GET", "/devices/oneplus-watch-3"))
        assertEquals(Route.Device("a b"), HttpProtocol.route("GET", "/devices/a%20b"))
    }

    @Test
    fun unknownPathsAndMethodsAreNotFound() {
        assertEquals(Route.NotFound, HttpProtocol.route("GET", "/"))
        assertEquals(Route.NotFound, HttpProtocol.route("GET", "/devices/"))
        assertEquals(Route.NotFound, HttpProtocol.route("GET", "/devices/a/b"))
        assertEquals(Route.NotFound, HttpProtocol.route("GET", "/devices/%zz"))
        assertEquals(Route.NotFound, HttpProtocol.route("POST", "/health"))
    }

    @Test
    fun bearerTokenMustMatchExactly() {
        assertTrue(HttpProtocol.isAuthorized("", null))
        assertTrue(HttpProtocol.isAuthorized("", "Bearer cualquiera"))
        assertTrue(HttpProtocol.isAuthorized("abc", "Bearer abc"))
        assertFalse(HttpProtocol.isAuthorized("abc", "Bearer abd"))
        assertFalse(HttpProtocol.isAuthorized("abc", "bearer abc"))
        assertFalse(HttpProtocol.isAuthorized("abc", "Bearer abc "))
        assertFalse(HttpProtocol.isAuthorized("abc", null))
    }

    @Test
    fun jsonResponseHasStatusLengthAndClose() {
        val body = "{\"error\":\"unauthorized\"}"
        val expected = "HTTP/1.1 401 Unauthorized\r\n" +
            "Content-Type: application/json\r\n" +
            "Content-Length: ${body.length}\r\n" +
            "Connection: close\r\n\r\n" + body
        assertArrayEquals(expected.toByteArray(Charsets.UTF_8), HttpProtocol.jsonResponse(401, body))
    }

    @Test
    fun contentLengthCountsUtf8Bytes() {
        val response = String(HttpProtocol.jsonResponse(200, "\"ñ\""), Charsets.UTF_8)
        assertTrue(response, response.contains("Content-Length: 4\r\n"))
    }

    @Test
    fun deviceNotFoundBodyEscapesTheId() {
        assertEquals(
            "{\"error\":\"device_not_found\",\"deviceId\":\"a\\\"b\"}",
            HttpProtocol.deviceNotFound("a\"b")
        )
    }

    @Test
    fun sseHeadMatchesPythonServer() {
        assertEquals(
            "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\n" +
                "X-Accel-Buffering: no\r\nConnection: keep-alive\r\n\r\n",
            HttpProtocol.SSE_HEAD
        )
    }

    @Test
    fun jsonStringEscapesControlCharacters() {
        assertEquals("\"a\\\"b\\\\c\\n\\u0001ñ\"", HttpProtocol.jsonString("a\"b\\c\n\u0001ñ"))
    }
}
