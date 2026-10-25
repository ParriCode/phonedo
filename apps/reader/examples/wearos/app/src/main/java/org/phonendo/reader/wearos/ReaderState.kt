// Estado que el servicio publica y la pantalla pinta. Un único StateFlow de
// proceso: el servicio y la actividad viven en el mismo proceso y así no hace
// falta enlazarlos (bind) solo para enseñar cuatro datos.
package org.phonendo.reader.wearos

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class UiState(
    val running: Boolean = false,
    val bpm: Double? = null,
    val availability: String? = null,
    val address: String? = null,
    val subscribers: Int = 0,
    val managers: Int = 0,
    val lastPost: String? = null,
    val error: String? = null,
)

object ReaderState {
    private val mutable = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = mutable.asStateFlow()

    fun update(change: (UiState) -> UiState) = mutable.update(change)
}
