// Fachada Kotlin del Reader nativo (libphonendo_reader.so, reader_jni.cpp).
//
// Es un object porque en C++ hay una sola instancia por proceso: init() la
// crea la primera vez y las siguientes llamadas la reutilizan, aunque el
// servicio se pare y vuelva a arrancar. El mutex de la capa JNI serializa
// todas las llamadas, así que esta clase se puede usar desde cualquier hilo.
// Las cadenas cruzan como UTF-8 en ByteArray.
package org.phonendo.reader.wearos

object NativeReader : ReaderPort {
    init {
        System.loadLibrary("phonendo_reader")
    }

    fun init(readerId: String, queueSize: Int = 64): Boolean =
        nativeInit(readerId.toByteArray(Charsets.UTF_8), queueSize)

    /** Sobre del evento para /newEvent, o null si la ingesta falla (ver lastError()). */
    fun ingestHeartRate(bpm: Double, epochMillis: Long): String? =
        nativeIngest(bpm, epochMillis)?.utf8()

    fun lastError(): String = nativeLastError()?.utf8().orEmpty()

    fun close() = nativeClose()

    val subscriberCount: Int get() = nativeSubscriberCount()

    override val connectedFrame: String by lazy { nativeSseConnected()!!.utf8() }
    override val heartbeatFrame: String by lazy { nativeSseHeartbeat()!!.utf8() }

    override fun metadataJson(): String = nativeMetadata()?.utf8().orEmpty()
    override fun devicesJson(): String = nativeDevices()?.utf8() ?: "[]"
    override fun deviceJson(deviceId: String): String? =
        nativeDevice(deviceId.toByteArray(Charsets.UTF_8))?.utf8()

    override fun subscribe(): Int = nativeSubscribe()
    override fun unsubscribe(id: Int) = nativeUnsubscribe(id)

    override fun poll(id: Int): StreamFrame? {
        val bytes = nativePollFrame(id) ?: return null
        // Primer byte: 'E' evento, 'C' cerrado (ver reader_jni.cpp).
        val text = String(bytes, 1, bytes.size - 1, Charsets.UTF_8)
        return if (bytes[0] == 'E'.code.toByte()) StreamFrame.Event(text) else StreamFrame.Closed(text)
    }

    private fun ByteArray.utf8() = String(this, Charsets.UTF_8)

    private external fun nativeInit(readerId: ByteArray, queueSize: Int): Boolean
    private external fun nativeIngest(bpm: Double, epochMillis: Long): ByteArray?
    private external fun nativeLastError(): ByteArray?
    private external fun nativeMetadata(): ByteArray?
    private external fun nativeDevices(): ByteArray?
    private external fun nativeDevice(deviceId: ByteArray): ByteArray?
    private external fun nativeSubscribe(): Int
    private external fun nativeUnsubscribe(id: Int)
    private external fun nativePollFrame(id: Int): ByteArray?
    private external fun nativeSubscriberCount(): Int
    private external fun nativeClose()
    private external fun nativeSseConnected(): ByteArray?
    private external fun nativeSseHeartbeat(): ByteArray?
}
