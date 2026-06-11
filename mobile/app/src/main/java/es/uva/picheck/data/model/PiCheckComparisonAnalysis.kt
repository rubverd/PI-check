package es.uva.picheck.data.model

data class PiCheckComparisonAnalysis(
    val comparisonId: String,
    val status: String,
    val message: String,
    val messages: List<String>,
    val appA: PiCheckVersionReport,
    val appB: PiCheckVersionReport,
    val rawJson: String,
    val comparisonJson: String? = null,
    val dashboard: ComparisonDashboard? = null,
    val comparisonArtifactPath: String? = null,
    val idIndiceAplicado: String? = null,
)
