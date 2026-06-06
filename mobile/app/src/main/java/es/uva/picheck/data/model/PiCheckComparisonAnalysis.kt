package es.uva.picheck.data.model

data class PiCheckComparisonAnalysis(
    val comparisonId: String,
    val status: String,
    val message: String,
    val messages: List<String>,
    val appA: PiCheckVersionReport,
    val appB: PiCheckVersionReport,
    val rawJson: String,
    val idIndiceAplicado: String? = null,
)
