package es.uva.picheck.data.model

data class ComparisonDashboard(
    val mastgScore: MastgScore? = null,
    val header: DashboardHeader? = null,
    val executiveSummary: List<String> = emptyList(),
    val quickKpis: List<QuickKpi> = emptyList(),
    val privacyMetrics: List<DashboardMetric> = emptyList(),
    val securityMetrics: List<DashboardMetric> = emptyList(),
    val exposureMetrics: List<DashboardMetric> = emptyList(),
    val technicalFindings: List<TechnicalFinding> = emptyList(),
)

data class DashboardHeader(
    val appName: String? = null,
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

data class MastgScore(
    val left: Float? = null,
    val right: Float? = null,
    val status: String? = null,
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
)

data class TechnicalFinding(
    val title: String,
    val severity: String? = null,
    val affectedSide: String? = null,
    val description: String? = null,
    val detail: String? = null,
    val masvs: String? = null,
    val cwe: String? = null,
)
