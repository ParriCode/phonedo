// Envío de cada evento a POST <manager>/newEvent, como manager_output.py y el
// ManagerOutput del ESP32: el cuerpo es el sobre del evento más "token".
//
// Cada Manager tiene su propio hilo y su cola acotada: uno caído o lento solo
// retrasa sus propios envíos, nunca los de los demás ni la ingesta (que no
// espera a la red). Si su cola se llena se descarta el evento más antiguo; el
// fallo se informa por onResult, nunca se lanza.
package org.phonendo.reader.wearos

import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit

data class PostResult(val url: String, val status: Int?, val error: String?) {
    val ok: Boolean get() = error == null && status != null && status in 200..299
}

/** Hace un POST JSON y devuelve el código HTTP; lanza si no hay respuesta. */
typealias PostTransport = (url: String, body: String) -> Int

class ManagerPoster(
    urls: List<String>,
    private val token: String,
    private val transport: PostTransport = ::httpPost,
    private val onResult: (PostResult) -> Unit = {},
    queueSize: Int = 32,
) {
    private val targets = urls.map { base ->
        val executor = ThreadPoolExecutor(
            1, 1, 0L, TimeUnit.MILLISECONDS,
            ArrayBlockingQueue(queueSize),
            { runnable -> Thread(runnable, "manager-$base").apply { isDaemon = true } },
            ThreadPoolExecutor.DiscardOldestPolicy(),
        )
        "$base/newEvent" to executor
    }

    val managerCount: Int get() = targets.size

    fun post(envelope: String) {
        if (targets.isEmpty()) return
        val body = newEventBody(envelope, token)
        for ((url, executor) in targets) {
            if (executor.isShutdown) continue
            executor.execute {
                val result = try {
                    PostResult(url, transport(url, body), null)
                } catch (error: Exception) {
                    PostResult(url, null, error.message ?: error.javaClass.simpleName)
                }
                onResult(result)
            }
        }
    }

    fun shutdown() {
        for ((_, executor) in targets) executor.shutdownNow()
    }

    companion object {
        const val TIMEOUT_MS = 5_000

        /** URLs separadas por comas, sin espacios ni "/" final; las vacías se ignoran. */
        fun parseUrls(list: String): List<String> =
            list.split(',').map { it.trim().trimEnd('/', ' ') }.filter { it.isNotEmpty() }

        /** {**sobre, "token": token}: el sobre es un objeto JSON compacto de C++. */
        fun newEventBody(envelope: String, token: String): String {
            val trimmed = envelope.trimEnd()
            require(trimmed.endsWith("}")) { "el sobre no es un objeto JSON" }
            val open = trimmed.dropLast(1)
            val separator = if (open.trimEnd().endsWith("{")) "" else ","
            return open + separator + "\"token\":" + HttpProtocol.jsonString(token) + "}"
        }

        fun httpPost(url: String, body: String): Int {
            val connection = URL(url).openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "POST"
                connection.connectTimeout = TIMEOUT_MS
                connection.readTimeout = TIMEOUT_MS
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                val bytes = body.toByteArray(Charsets.UTF_8)
                connection.setFixedLengthStreamingMode(bytes.size)
                connection.outputStream.use { it.write(bytes) }
                val status = connection.responseCode
                // Vaciar la respuesta deja reutilizar la conexión.
                (if (status >= 400) connection.errorStream else connection.inputStream)?.use { it.readBytes() }
                return status
            } finally {
                connection.disconnect()
            }
        }
    }
}
