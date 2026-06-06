package es.uva.picheck.data.model

data class ComparisonAnalysisResult(
    val comparisonId: String,
    val status: String,
    val message: String,
    val messages: List<String>,
    val appA: VersionReportInfo,
    val appB: VersionReportInfo,
    val rawJson: String,
    val idIndiceAplicado: String? = null,
)
