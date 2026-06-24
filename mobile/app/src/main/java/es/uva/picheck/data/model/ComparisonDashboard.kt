package es.uva.picheck.data.model

data class ComparisonDashboard(
    val mastgScore: MastgScore? = null,
    val header: DashboardHeader? = null,
    val executiveSummary: List<String> = emptyList(),
    val verdictCards: List<DashboardVerdictCard> = emptyList(),
    val quickKpis: List<QuickKpi> = emptyList(),
    val platformMetrics: List<DashboardMetric> = emptyList(),
    val privacyMetrics: List<DashboardMetric> = emptyList(),
    val securityMetrics: List<DashboardMetric> = emptyList(),
    val exposureMetrics: List<DashboardMetric> = emptyList(),
    val keyFindings: List<TechnicalFinding> = emptyList(),
    val technicalFindings: List<TechnicalFinding> = emptyList(),
    val permissionDiff: PermissionDiff? = null,
    val technicalSummary: DashboardTechnicalSummary? = null,
)

data class DashboardHeader(
    val appName: String? = null,
    val left: DashboardSide? = null,
    val right: DashboardSide? = null,
    val leftTitle: String? = null,
    val rightTitle: String? = null,
    val leftVersion: String? = null,
    val rightVersion: String? = null,
    val leftIntegrationModel: String? = null,
    val rightIntegrationModel: String? = null,
    val leftMobsfStatus: String? = null,
    val rightMobsfStatus: String? = null,
    val leftIcon: String? = null,
    val rightIcon: String? = null,
)

data class DashboardSide(
    val label: String? = null,
    val appId: String? = null,
    val version: String? = null,
    val versionCode: Int? = null,
    val integrationModel: String? = null,
    val integrationModelShort: String? = null,
    val mobsfStatus: String? = null,
    val icon: String? = null,
)

data class MastgScore(
    val left: Float? = null,
    val right: Float? = null,
    val status: String? = null,
    val label: String? = null,
)

data class DashboardVerdictCard(
    val title: String,
    val winner: String? = null,
    val status: String? = null,
    val summary: String? = null,
)

data class QuickKpi(
    val title: String,
    val leftLabel: String? = null,
    val rightLabel: String? = null,
    val leftValue: Float? = null,
    val rightValue: Float? = null,
    val winner: String? = null,
    val level: String? = null,
)

data class DashboardMetric(
    val label: String,
    val leftValue: Float? = null,
    val rightValue: Float? = null,
    val leftLabel: String? = null,
    val rightLabel: String? = null,
    val preferred: String? = null,
    val leftExamples: List<String> = emptyList(),
    val rightExamples: List<String> = emptyList(),
    val examplesTruncated: Boolean = false,
)

data class TechnicalFinding(
    val title: String,
    val severity: String? = null,
    val affectedSide: String? = null,
    val description: String? = null,
    val detail: String? = null,
    val summary: String? = null,
    val category: String? = null,
    val mastgRelation: String? = null,
    val relationType: String? = null,
    val masvs: String? = null,
    val cwe: String? = null,
)

data class PermissionDiff(
    val addedInLeft: List<String> = emptyList(),
    val removedInLeft: List<String> = emptyList(),
    val healthConnectPermissions: List<String> = emptyList(),
)

data class DashboardTechnicalSummary(
    val leftReportAvailable: Boolean? = null,
    val rightReportAvailable: Boolean? = null,
    val leftReportSizeBytes: Long? = null,
    val rightReportSizeBytes: Long? = null,
    val rawReportInResponse: Boolean? = null,
)


data class MastgTestRow(
    val id: String,
    val title: String,
    val relationType: String,
    val leftStatus: MastgTestStatus,
    val rightStatus: MastgTestStatus,
    val evidence: String? = null,
)

enum class MastgTestStatus {
    PASS,
    FAIL,
    REVIEW,
    NOT_EVALUABLE,
    ERROR
}
