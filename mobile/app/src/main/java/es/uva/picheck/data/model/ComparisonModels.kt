package es.uva.picheck.data.model

data class ComparisonAnalysisResult(
    val comparisonId: String,
    val status: String,
    val message: String,
    val messages: List<String>,
    val appA: VersionReportInfo,
    val appB: VersionReportInfo,
    val idIndiceAplicado: String? = null,
    val rawJson: String,
)

data class VersionReportInfo(
    val versionApp: VersionAppInfo,
    val mobsfReport: MobSFReportInfo,
)

data class VersionAppInfo(
    val idApp: String,
    val version: String,
    val versionCode: Int? = null,
    val fechaVersion: String? = null,
    val categoria: String? = null,
    val modeloIntegracion: String,
    val apkSha256: String? = null,
    val estadoMobsf: String,
    val hashMobsf: String? = null,
    val rutaInformeMobsf: String? = null,
    val rutaApk: String? = null,
)

data class MobSFReportInfo(
    val available: Boolean,
    val hashMobsf: String? = null,
    val rutaInforme: String? = null,
    val fileName: String? = null,
    val scanType: String? = null,
    val jsonReportRaw: String? = null,
)
