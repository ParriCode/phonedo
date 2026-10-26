// Servidor HTTP/1.1 mínimo del reloj sobre un ServerSocket, un hilo por
// conexión. Sirve /health, /metadata, /devices, /devices/{id} y /stream con
// el contrato del Reader Python y del ESP32; la lógica de rutas y respuestas
// está en HttpProtocol y la de cada cliente SSE en SseSession.
//
// Invariantes: cada respuesta JSON cierra la conexión; /stream admite como
// mucho maxStreamClients a la vez (el siguiente recibe 503, como
// PHONENDO_MAX_SSE_CLIENTS); stop() cierra el socket de escucha y todas las
// conexiones abiertas, lo que despierta a sus hilos.
package org.phonendo.reader.wearos

import android.util.Log
import java.io.BufferedInputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.Collections
import java.util.concurrent.atomic.AtomicInteger

class ReaderHttpServer(
    private val reader: ReaderPort,
    private val port: Int,
    private val token: String,
    private val onSubscribersChanged: (Int) -> Unit = {},
    private val maxStreamClients: Int = 4,
) {
    @Volatile private var serverSocket: ServerSocket? = null
    private val sockets = Collections.synchronizedSet(HashSet<Socket>())
    private val streamClients = AtomicInteger(0)

    fun start() {
        if (serverSocket != null) return
        val socket = ServerSocket().apply {
            reuseAddress = true
            bind(InetSocketAddress(port))
        }
        serverSocket = socket
        Thread({ acceptLoop(socket) }, "http-accept").apply { isDaemon = true }.start()
        Log.i(TAG, "Servidor HTTP en el puerto $port: /health /metadata /devices /stream")
    }

    fun stop() {
        serverSocket?.closeQuietly()
        serverSocket = null
        synchronized(sockets) { sockets.toList() }.forEach { it.closeQuietly() }
    }

    private fun acceptLoop(listener: ServerSocket) {
        while (!listener.isClosed) {
            val client = try {
                listener.accept()
            } catch (_: IOException) {
                break
            }
            sockets += client
            Thread({ handle(client) }, "http-${client.port}").apply { isDaemon = true }.start()
        }
    }

    private fun handle(socket: Socket) {
        try {
            socket.soTimeout = READ_TIMEOUT_MS
            val input = BufferedInputStream(socket.getInputStream())
            val output = socket.getOutputStream()
            val request = readHead(input)?.let(HttpProtocol::parseHead)
            if (request == null) {
                output.write(HttpProtocol.jsonResponse(400, HttpProtocol.BAD_REQUEST))
                return
            }
            if (!HttpProtocol.isAuthorized(token, request.header("Authorization"))) {
                output.write(HttpProtocol.jsonResponse(401, HttpProtocol.UNAUTHORIZED))
                return
            }
            when (val route = HttpProtocol.route(request.method, request.path)) {
                Route.Health -> output.write(HttpProtocol.jsonResponse(200, HttpProtocol.HEALTH_OK))
                Route.Metadata -> output.write(HttpProtocol.jsonResponse(200, reader.metadataJson()))
                Route.Devices -> output.write(HttpProtocol.jsonResponse(200, reader.devicesJson()))
                is Route.Device -> {
                    val body = reader.deviceJson(route.id)
                    output.write(
                        if (body != null) HttpProtocol.jsonResponse(200, body)
                        else HttpProtocol.jsonResponse(404, HttpProtocol.deviceNotFound(route.id))
                    )
                }
                Route.Stream -> serveStream(socket, output)
                Route.NotFound -> output.write(HttpProtocol.jsonResponse(404, HttpProtocol.NOT_FOUND))
            }
            output.flush()
        } catch (error: IOException) {
            Log.d(TAG, "Conexión cerrada: ${error.message}")
        } catch (error: RuntimeException) {
            Log.w(TAG, "Error atendiendo la petición", error)
        } finally {
            sockets -= socket
            socket.closeQuietly()
        }
    }

    private fun serveStream(socket: Socket, output: OutputStream) {
        if (streamClients.incrementAndGet() > maxStreamClients) {
            streamClients.decrementAndGet()
            output.write(HttpProtocol.jsonResponse(503, HttpProtocol.TOO_MANY_SUBSCRIBERS))
            return
        }
        try {
            val id = reader.subscribe()
            if (id == 0) {
                output.write(HttpProtocol.jsonResponse(503, HttpProtocol.STREAM_UNAVAILABLE))
                return
            }
            onSubscribersChanged(streamClients.get())
            Log.i(TAG, "SSE: suscriptor $id conectado (${streamClients.get()} activos)")
            // Sin timeout de lectura: el cliente no envía nada más.
            socket.soTimeout = 0
            output.write(HttpProtocol.SSE_HEAD.toByteArray(Charsets.UTF_8))
            val session = SseSession(reader, id, { frame -> writeFrame(output, frame) }, System::currentTimeMillis)
            try {
                if (session.open()) {
                    while (!socket.isClosed && session.step()) Thread.sleep(POLL_INTERVAL_MS)
                }
            } catch (_: InterruptedException) {
                Thread.currentThread().interrupt()
            } finally {
                session.finish()
                Log.i(TAG, "SSE: suscriptor $id desconectado")
            }
        } finally {
            onSubscribersChanged(streamClients.decrementAndGet())
        }
    }

    private fun writeFrame(output: OutputStream, frame: String): Boolean = try {
        output.write(frame.toByteArray(Charsets.UTF_8))
        output.flush()
        true
    } catch (_: IOException) {
        false
    }

    /** Líneas de la cabecera hasta la línea vacía; null si excede el límite o se corta. */
    private fun readHead(input: InputStream): List<String>? {
        val lines = ArrayList<String>()
        val line = StringBuilder()
        var total = 0
        while (true) {
            val b = input.read()
            if (b < 0) return null
            if (++total > MAX_HEAD_BYTES) return null
            when (b) {
                '\r'.code -> continue
                '\n'.code -> {
                    if (line.isEmpty()) return lines
                    lines += line.toString()
                    line.setLength(0)
                }
                else -> line.append(b.toChar())
            }
        }
    }

    private fun java.io.Closeable.closeQuietly() {
        try {
            close()
        } catch (_: IOException) {
        }
    }

    companion object {
        private const val TAG = "PhonendoReader"
        private const val READ_TIMEOUT_MS = 10_000
        private const val MAX_HEAD_BYTES = 8 * 1024
        private const val POLL_INTERVAL_MS = 100L
    }
}
