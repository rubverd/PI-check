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
)
