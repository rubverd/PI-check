package es.uva.picheck.data.model

data class DeviceAppInfo(
    val name: String,
    val packageName: String,
    val sourceDir: String,
    val splitSourceDirs: List<String> = emptyList(),
)
