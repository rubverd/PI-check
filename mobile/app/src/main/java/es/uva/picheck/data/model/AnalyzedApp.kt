package es.uva.picheck.data.model

enum class IntegrationModel {
    LEGACY,
    HEALTH_CONNECT,
    UNKNOWN,
}

data class RegisteredAppVersion(
    val version: String,
    val versionCode: Int? = null,
    val versionDate: String? = null,
    val integrationModel: IntegrationModel,
    val integrationModelShort: String,
    val mobsfStatus: String? = null,
    val mobsfReportAvailable: Boolean = false,
    val apkSha256: String? = null,
    val rutaApk: String? = null,
)

data class AnalyzedApp(
    val appId: String,
    val name: String,
    val developer: String? = null,
    val icon: String? = null,
    val version: String,
    val category: String,
    val analysisDate: String,
    val integrationModel: IntegrationModel,
    val mobsfStatus: String? = null,
    val mobsfReportAvailable: Boolean = false,
    val versions: List<RegisteredAppVersion> = emptyList(),
)