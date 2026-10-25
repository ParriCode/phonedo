// Pantalla mínima del reloj: pulso actual, botón de empezar/parar, IP:puerto
// del servidor, suscriptores SSE y resultado del último POST a un Manager.
//
// La actividad solo pide permisos y arranca o para HeartRateService; todo el
// estado lo publica el servicio en ReaderState. BODY_SENSORS es obligatorio
// antes de arrancar: un servicio de tipo health sin él muere con
// SecurityException al llamar a startForeground.
package org.phonendo.reader.wearos

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.core.content.ContextCompat
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.material.Chip
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Text

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                ReaderScreen()
            }
        }
    }
}

private val requiredPermissions: Array<String> =
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        arrayOf(Manifest.permission.BODY_SENSORS, Manifest.permission.POST_NOTIFICATIONS)
    } else {
        arrayOf(Manifest.permission.BODY_SENSORS)
    }

@Composable
private fun ReaderScreen() {
    val context = LocalContext.current
    val state by ReaderState.state.collectAsState()
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        if (granted[Manifest.permission.BODY_SENSORS] == true) {
            HeartRateService.start(context)
        } else {
            ReaderState.update { it.copy(error = "Sin permiso de sensores corporales") }
        }
    }

    ScalingLazyColumn(modifier = Modifier.fillMaxWidth()) {
        item {
            Text(
                text = state.bpm?.let { "%.0f bpm".format(it) } ?: "-- bpm",
                style = MaterialTheme.typography.display2,
                textAlign = TextAlign.Center,
            )
        }
        item {
            Chip(
                label = { Text(if (state.running) "Parar" else "Empezar") },
                onClick = {
                    if (state.running) {
                        HeartRateService.stop(context)
                    } else if (ContextCompat.checkSelfPermission(context, Manifest.permission.BODY_SENSORS)
                        == PackageManager.PERMISSION_GRANTED
                    ) {
                        HeartRateService.start(context)
                    } else {
                        launcher.launch(requiredPermissions)
                    }
                },
            )
        }
        item { Line(state.address ?: if (state.running) "Sin Wi-Fi" else "Parado") }
        item { Line("Suscriptores: ${state.subscribers}") }
        item { Line("Managers: ${state.managers}") }
        item { Line("POST: ${state.lastPost ?: "-"}") }
        state.availability?.let { item { Line(it) } }
        state.error?.let { item { Line(it, MaterialTheme.colors.error) } }
    }
}

@Composable
private fun Line(text: String, color: androidx.compose.ui.graphics.Color = MaterialTheme.colors.onBackground) {
    Text(
        text = text,
        color = color,
        style = MaterialTheme.typography.caption2,
        textAlign = TextAlign.Center,
        modifier = Modifier.fillMaxWidth(),
    )
}
