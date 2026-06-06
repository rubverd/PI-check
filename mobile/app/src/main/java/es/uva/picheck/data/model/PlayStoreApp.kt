package es.uva.picheck.data.model

data class PlayStoreApp(
    val appId: String,
    val title: String,
    val developer: String? = null,
    val icon: String? = null,
    val score: Double? = null,
    val genre: String? = null,
    val free: Boolean? = null,
    val url: String? = null,
    val version: String? = null,
    val versionDate: String? = null,
    val selectedVersion: String? = null,
    val versionCode: Int? = null,
    val integrationModel: IntegrationModel? = null,
    val apkSha256: String? = null,
)
