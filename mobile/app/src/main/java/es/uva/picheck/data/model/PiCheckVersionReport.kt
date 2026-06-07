package es.uva.picheck.data.model

data class PiCheckVersionReport(
    val versionApp: PiCheckVersionAppInfo,
    val mobsfReport: PiCheckMobSFReport,
)
