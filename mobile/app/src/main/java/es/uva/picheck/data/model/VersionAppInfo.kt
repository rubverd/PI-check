package es.uva.picheck.data.model

data class VersionAppInfo(
    val idApp: String,
    val version: String,
    val modeloIntegracion: String,
    val estadoMobsf: String,
    val versionCode: Int? = null,
    val fechaVersion: String? = null,
    val categoria: String? = null,
    val apkSha256: String? = null,
    val hashMobsf: String? = null,
    val rutaInformeMobsf: String? = null,
    val rutaApk: String? = null,
)
