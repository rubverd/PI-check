package es.uva.picheck.data.model

data class MobSFReportInfo(
    val available: Boolean,
    val hashMobsf: String? = null,
    val rutaInforme: String? = null,
    val fileName: String? = null,
    val scanType: String? = null,
    val jsonReportRaw: String? = null,
)
