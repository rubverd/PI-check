package es.uva.picheck.data.model

enum class IntegrationModel {
    LEGACY,
    HEALTH_CONNECT,
}

data class AnalyzedApp(
    val appId: String,
    val name: String,
    val version: String,
    val category: String,
    val analysisDate: String,
    val integrationModel: IntegrationModel,
)
