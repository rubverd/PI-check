package es.uva.picheck.data.remote

import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.PlayStoreApp

object PiCheckApiClient {
    suspend fun searchApps(query: String): List<PlayStoreApp> {
        // TODO: Sustituir por llamada real HTTP al backend.
        return emptyList()
    }

    suspend fun requestComparison(
        appA: PlayStoreApp,
        appB: PlayStoreApp,
        downloadApks: Boolean,
    ): String {
        // TODO: Sustituir por llamada real HTTP al backend.
        return "Comparación solicitada: ${appA.title} vs ${appB.title}"
    }

    suspend fun getAnalyzedApps(): List<AnalyzedApp> {
        // TODO: Consumir endpoint real cuando exista base de datos.
        return emptyList()
    }
}
