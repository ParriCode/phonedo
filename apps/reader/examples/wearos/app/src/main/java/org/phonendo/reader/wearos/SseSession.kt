// Una conexión /stream: el equivalente de drainClients() del ESP32 para un
// solo cliente, con el reloj y la escritura inyectados para probarlo sin red.
//
// Invariantes: ": connected" es lo primero que se escribe; tras
// heartbeatMs sin escribir nada se manda ": heartbeat" (como el timeout de
// 15 s de server.py); "stream_closed" o un fallo de escritura terminan la
// sesión; finish() da de baja al suscriptor una sola vez.
package org.phonendo.reader.wearos

class SseSession(
    private val stream: StreamPort,
    private val id: Int,
    private val write: (String) -> Boolean,
    private val clock: () -> Long,
    private val heartbeatMs: Long = HEARTBEAT_MS,
) {
    private var lastWrite = 0L
    private var finished = false

    fun open(): Boolean = send(stream.connectedFrame)

    /** Vacía lo pendiente y manda el latido si toca; false si hay que cerrar. */
    fun step(): Boolean {
        while (true) {
            when (val frame = stream.poll(id)) {
                null -> break
                is StreamFrame.Event -> if (!send(frame.text)) return false
                is StreamFrame.Closed -> {
                    send(frame.text)
                    return false
                }
            }
        }
        if (clock() - lastWrite >= heartbeatMs) return send(stream.heartbeatFrame)
        return true
    }

    fun finish() {
        if (finished) return
        finished = true
        stream.unsubscribe(id)
    }

    private fun send(text: String): Boolean {
        lastWrite = clock()
        return write(text)
    }

    companion object {
        const val HEARTBEAT_MS = 15_000L
    }
}
