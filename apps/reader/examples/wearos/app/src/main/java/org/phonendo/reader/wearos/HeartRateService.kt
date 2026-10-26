// Servicio en primer plano (tipo health) que mantiene vivo el Reader mientras
// mide: el equivalente de setup() y loop() del ESP32.
//
// Health Services entrega cada muestra de HEART_RATE_BPM; el Reader nativo la
// convierte en observación y la publica en el stream, y el sobre que devuelve
// se manda a los Managers en segundo plano. Mientras corre, el servicio pide
// la red Wi-Fi (Wear OS la apaga si el reloj tiene Bluetooth con el móvil) y
// un wake lock parcial para que el servidor siga respondiendo con la pantalla
// apagada. Al parar, primero cierra el stream para que cada cliente SSE reciba
// stream_closed y después cierra los sockets.
package org.phonendo.reader.wearos

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.health.services.client.HealthServices
import androidx.health.services.client.MeasureCallback
import androidx.health.services.client.MeasureClient
import androidx.health.services.client.data.Availability
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.DeltaDataType
import java.io.IOException
import java.net.Inet4Address
import java.net.NetworkInterface
import java.time.Instant

class HeartRateService : Service() {
    private var measureClient: MeasureClient? = null
    private var server: ReaderHttpServer? = null
    private var poster: ManagerPoster? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiCallback: ConnectivityManager.NetworkCallback? = null
    private val handler = Handler(Looper.getMainLooper())

    private val measureCallback = object : MeasureCallback {
        override fun onAvailabilityChanged(dataType: DeltaDataType<*, *>, availability: Availability) {
            ReaderState.update { it.copy(availability = availability.toString()) }
        }

        override fun onDataReceived(data: DataPointContainer) {
            // Las muestras traen el tiempo desde el arranque; el instante de
            // arranque en epoch lo convierte en hora real.
            val boot = Instant.ofEpochMilli(System.currentTimeMillis() - SystemClock.elapsedRealtime())
            for (point in data.getData(DataType.HEART_RATE_BPM)) {
                publish(point.value, point.getTimeInstant(boot).toEpochMilli())
            }
        }

        override fun onRegistrationFailed(throwable: Throwable) {
            Log.e(TAG, "Health Services rechazó la medida de pulso", throwable)
            ReaderState.update { it.copy(error = "Health Services: ${throwable.message}") }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> stopReader()
            else -> startReader()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        if (server != null) stopReader()
        super.onDestroy()
    }

    private fun startReader() {
        if (server != null) return
        ServiceCompat.startForeground(
            this, NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_HEALTH
        )
        ReaderState.update { UiState(running = true) }

        if (!NativeReader.init(BuildConfig.READER_ID)) {
            reportError("Reader nativo: ${NativeReader.lastError()}")
        }
        val urls = ManagerPoster.parseUrls(BuildConfig.MANAGER_URLS)
        poster = ManagerPoster(urls, BuildConfig.MANAGER_TOKEN, onResult = ::onPostResult)
        ReaderState.update { it.copy(managers = urls.size) }

        val http = ReaderHttpServer(NativeReader, BuildConfig.READER_PORT, BuildConfig.READER_TOKEN, { count ->
            ReaderState.update { it.copy(subscribers = count) }
        })
        try {
            http.start()
            server = http
        } catch (error: IOException) {
            reportError("No se pudo abrir el puerto ${BuildConfig.READER_PORT}: ${error.message}")
        }

        requestWifi()
        acquireWakeLock()
        measureClient = HealthServices.getClient(this).measureClient.also {
            it.registerMeasureCallback(DataType.HEART_RATE_BPM, measureCallback)
        }
        Log.i(TAG, "Reader ${BuildConfig.READER_ID} en marcha; Managers configurados: ${urls.size}")
    }

    private fun stopReader() {
        measureClient?.unregisterMeasureCallbackAsync(DataType.HEART_RATE_BPM, measureCallback)
        measureClient = null
        poster?.shutdown()
        poster = null
        // stream_closed a los clientes SSE antes de cerrar sus sockets.
        NativeReader.close()
        val http = server
        server = null
        handler.postDelayed({ http?.stop() }, CLOSE_GRACE_MS)
        releaseWifi()
        wakeLock?.let { if (it.isHeld) it.release() }
        wakeLock = null
        ReaderState.update { it.copy(running = false, subscribers = 0) }
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun publish(bpm: Double, epochMillis: Long) {
        // Health Services manda 0 mientras aún no ha captado el pulso.
        if (!bpm.isFinite() || bpm <= 0.0) return
        val envelope = NativeReader.ingestHeartRate(bpm, epochMillis)
        if (envelope == null) {
            reportError("Ingesta: ${NativeReader.lastError()}")
            return
        }
        ReaderState.update { it.copy(bpm = bpm, error = null) }
        poster?.post(envelope)
    }

    private fun onPostResult(result: PostResult) {
        val text = if (result.ok) "${result.status} ${result.url}"
        else "fallo ${result.status ?: result.error} ${result.url}"
        if (!result.ok) Log.w(TAG, "Manager: $text")
        ReaderState.update { it.copy(lastPost = text) }
    }

    private fun reportError(message: String) {
        Log.e(TAG, message)
        ReaderState.update { it.copy(error = message) }
    }

    private fun requestWifi() {
        val connectivity = getSystemService(ConnectivityManager::class.java)
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onLinkPropertiesChanged(network: Network, properties: LinkProperties) {
                val ip = properties.linkAddresses.map { it.address }.firstOrNull { it is Inet4Address }
                ReaderState.update { it.copy(address = ip?.hostAddress?.let { host -> "$host:${BuildConfig.READER_PORT}" }) }
            }

            override fun onLost(network: Network) {
                ReaderState.update { it.copy(address = null) }
            }
        }
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        try {
            connectivity.requestNetwork(request, callback)
            wifiCallback = callback
        } catch (error: SecurityException) {
            Log.w(TAG, "Sin permiso para pedir la red Wi-Fi", error)
        }
        // Hasta que llegue el callback, la dirección de wlan0 si ya hay Wi-Fi.
        currentWifiAddress()?.let { ip ->
            ReaderState.update { it.copy(address = "$ip:${BuildConfig.READER_PORT}") }
        }
    }

    private fun releaseWifi() {
        wifiCallback?.let { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) }
        wifiCallback = null
    }

    private fun currentWifiAddress(): String? = try {
        NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
            .filter { it.isUp && !it.isLoopback && it.name.startsWith("wlan") }
            .flatMap { it.inetAddresses.toList() }
            .firstOrNull { it is Inet4Address }?.hostAddress
    } catch (_: Exception) {
        null
    }

    private fun acquireWakeLock() {
        val power = getSystemService(PowerManager::class.java)
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "phonendo:reader").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun notification(): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW)
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_heart)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notification_text))
            .setContentIntent(open)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_WORKOUT)
            .build()
    }

    companion object {
        private const val TAG = "PhonendoReader"
        private const val CHANNEL_ID = "reader"
        private const val NOTIFICATION_ID = 1
        private const val CLOSE_GRACE_MS = 500L
        private const val ACTION_START = "org.phonendo.reader.wearos.START"
        private const val ACTION_STOP = "org.phonendo.reader.wearos.STOP"

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context, Intent(context, HeartRateService::class.java).setAction(ACTION_START)
            )
        }

        fun stop(context: Context) {
            context.startService(Intent(context, HeartRateService::class.java).setAction(ACTION_STOP))
        }
    }
}
