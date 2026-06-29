package es.uva.picheck.data.local.history

import es.uva.picheck.data.model.DashboardSide
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import java.util.UUID

/**
 * El historial se almacena en Room usando el JSON original de la respuesta de comparativa.
 * Esto permite reconstruir la pantalla de resultados sin repetir análisis ni llamar al backend.
 */
fun PiCheckComparisonAnalysis.toHistoryEntity(
    createdAtMillis: Long = System.currentTimeMillis(),
): ComparisonHistoryEntity {
    val leftHeader = dashboard?.header?.left
    val rightHeader = dashboard?.header?.right
    val leftVersion = appA.versionApp
    val rightVersion = appB.versionApp
    val fallbackId = UUID.nameUUIDFromBytes(
        listOf(leftVersion.idApp, leftVersion.version, rightVersion.idApp, rightVersion.version, rawJson)
            .joinToString("|")
            .toByteArray(),
    ).toString()

    return ComparisonHistoryEntity(
        id = comparisonId.takeIf { it.isNotBlank() } ?: fallbackId,
        createdAtMillis = createdAtMillis,
        leftAppId = leftHeader?.appId.nonBlankOr(leftVersion.idApp),
        leftName = leftHeader.displayName().nonBlankOr(leftVersion.idApp),
        leftVersion = leftHeader?.version ?: leftVersion.version,
        leftIntegrationModel = leftHeader?.integrationModel ?: leftVersion.modeloIntegracion,
        leftIcon = leftHeader?.icon ?: dashboard?.header?.leftIcon,
        rightAppId = rightHeader?.appId.nonBlankOr(rightVersion.idApp),
        rightName = rightHeader.displayName().nonBlankOr(rightVersion.idApp),
        rightVersion = rightHeader?.version ?: rightVersion.version,
        rightIntegrationModel = rightHeader?.integrationModel ?: rightVersion.modeloIntegracion,
        rightIcon = rightHeader?.icon ?: dashboard?.header?.rightIcon,
        mastgIndexId = dashboard?.mastg?.indexId ?: dashboard?.mastgScore?.indexId ?: idIndiceAplicado,
        mastgIndexName = dashboard?.mastg?.label ?: dashboard?.mastgScore?.label,
        rawJson = rawJson,
        comparisonJson = comparisonJson,
    )
}

private fun DashboardSide?.displayName(): String? {
    val side = this ?: return null
    return listOf(side.name, side.appName, side.title, side.label, side.appId)
        .firstOrNull { !it.isNullOrBlank() }
}

private fun String?.nonBlankOr(fallback: String): String = takeUnless { it.isNullOrBlank() } ?: fallback
