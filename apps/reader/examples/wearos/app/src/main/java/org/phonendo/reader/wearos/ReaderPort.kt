// Puertos que separan la parte Android del Reader nativo.
//
// El servidor HTTP y las sesiones SSE solo conocen estas interfaces; en la app
// las implementa NativeReader (JNI) y en las pruebas JVM, dobles en memoria.
// Las tramas SSE las construye C++ (reader_stream.cpp), así que aquí viajan ya
// formateadas y Kotlin solo decide cuándo escribirlas.
package org.phonendo.reader.wearos

sealed interface StreamFrame {
    val text: String

    /** "event: observation ..." */
    data class Event(override val text: String) : StreamFrame

    /** "event: stream_closed ...": la cola se desbordó o el stream se cerró. */
    data class Closed(override val text: String) : StreamFrame
}

interface StreamPort {
    val connectedFrame: String
    val heartbeatFrame: String

    /** 0 si no hay stream disponible. */
    fun subscribe(): Int
    fun unsubscribe(id: Int)

    /** null mientras no haya nada pendiente. */
    fun poll(id: Int): StreamFrame?
}

interface ReaderPort : StreamPort {
    fun metadataJson(): String
    fun devicesJson(): String

    /** null si el dispositivo no existe. */
    fun deviceJson(deviceId: String): String?
}
