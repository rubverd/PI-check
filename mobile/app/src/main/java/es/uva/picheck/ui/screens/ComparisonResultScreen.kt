package es.uva.picheck.ui.screens

import android.util.Log
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.stickyHeader
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import es.uva.picheck.data.model.ComparisonDashboard
import es.uva.picheck.data.model.DashboardMetric
import es.uva.picheck.data.model.DashboardSide
import es.uva.picheck.data.model.DashboardVerdictCard
import es.uva.picheck.data.model.MastgTestRow
import es.uva.picheck.data.model.MastgTestStatus
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckCompareLeft
import es.uva.picheck.ui.theme.PiCheckCompareLeftBg
import es.uva.picheck.ui.theme.PiCheckCompareRight
import es.uva.picheck.ui.theme.PiCheckCompareRightBg
import es.uva.picheck.ui.theme.PiCheckHealthConnect
import es.uva.picheck.ui.theme.PiCheckHealthConnectBg
import es.uva.picheck.ui.theme.PiCheckDarkText
import es.uva.picheck.ui.theme.PiCheckLegacy
import es.uva.picheck.ui.theme.PiCheckLegacyBg
import es.uva.picheck.ui.theme.PiCheckLegacyGray
import es.uva.picheck.ui.theme.PiCheckModelLegacy
import es.uva.picheck.ui.theme.PiCheckModelNeutral
import es.uva.picheck.ui.theme.PiCheckRiskHigh
import es.uva.picheck.ui.theme.PiCheckSuccess
import es.uva.picheck.ui.theme.PiCheckWarning
import kotlin.math.max

private enum class ComparisonTab { GENERAL, MASTG }

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ComparisonResultScreen(result: PiCheckComparisonAnalysis, onNewComparison: () -> Unit) {
    val dashboard = result.dashboard
    val (leftSide, rightSide) = comparisonSides(result, dashboard)
    val (leftColors, rightColors) = resolveComparisonColors(leftSide, rightSide)
    Log.d(
        "PiCheckDashboardUI",
        "Rendering dashboard. platform=${dashboard?.platformMetrics?.size ?: 0}, privacy=${dashboard?.privacyMetrics?.size ?: 0}, security=${dashboard?.securityMetrics?.size ?: 0}, exposure=${dashboard?.exposureMetrics?.size ?: 0}",
    )
    var selectedTab by remember { mutableStateOf(ComparisonTab.GENERAL) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Dashboard de comparativa", color = Color.White, fontWeight = FontWeight.Bold) }, colors = TopAppBarDefaults.topAppBarColors(containerColor = PiCheckBurgundy)) },
        containerColor = PiCheckBackground,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.padding(innerPadding).padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            stickyHeader { CompactComparisonHeader(leftSide, rightSide, leftColors, rightColors) }
            item { ComparisonTabSelector(selectedTab) { selectedTab = it } }
            item {
                Crossfade(targetState = selectedTab, label = "comparison-tab") { tab ->
                    when (tab) {
                        ComparisonTab.GENERAL -> GeneralTab(result, dashboard, leftSide, rightSide, leftColors, rightColors)
                        ComparisonTab.MASTG -> MastgIndexTab(
                            dashboard = dashboard,
                            leftName = sideDisplayName(leftSide),
                            rightName = sideDisplayName(rightSide),
                            leftColor = leftColors.accent,
                            rightColor = rightColors.accent,
                            leftColors = leftColors,
                            rightColors = rightColors,
                        )
                    }
                }
            }
            item {
                Button(onClick = onNewComparison, colors = ButtonDefaults.buttonColors(containerColor = PiCheckBlue, contentColor = Color.White), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                    Text("Realizar nueva comparativa", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

private data class ComparisonSideColors(
    val accent: Color,
    val background: Color,
    val border: Color,
    val modelColor: Color,
)

private fun comparisonSides(
    result: PiCheckComparisonAnalysis,
    dashboard: ComparisonDashboard?,
): Pair<DashboardSide, DashboardSide> = Pair(
    dashboard?.header?.left ?: DashboardSide(
        label = result.appA.versionApp.idApp,
        appId = result.appA.versionApp.idApp,
        version = result.appA.versionApp.version,
        integrationModel = result.appA.versionApp.modeloIntegracion,
        mobsfStatus = result.appA.versionApp.estadoMobsf,
    ),
    dashboard?.header?.right ?: DashboardSide(
        label = result.appB.versionApp.idApp,
        appId = result.appB.versionApp.idApp,
        version = result.appB.versionApp.version,
        integrationModel = result.appB.versionApp.modeloIntegracion,
        mobsfStatus = result.appB.versionApp.estadoMobsf,
    ),
)

private fun resolveComparisonColors(
    left: DashboardSide,
    right: DashboardSide,
): Pair<ComparisonSideColors, ComparisonSideColors> {
    val sameApp = !left.appId.isNullOrBlank() && left.appId.equals(right.appId, ignoreCase = true)
    val leftIsHC = isHealthConnectModel(left.integrationModel)
    val rightIsHC = isHealthConnectModel(right.integrationModel)
    val leftIsLegacy = isLegacyModel(left.integrationModel)
    val rightIsLegacy = isLegacyModel(right.integrationModel)
    val isEvolutionComparison = sameApp && leftIsHC != rightIsHC && (leftIsLegacy || rightIsLegacy)

    Log.d("PiCheckDashboardUI", "sameApp=$sameApp isEvolutionComparison=$isEvolutionComparison")
    Log.d("PiCheckDashboardUI", "leftName=${appDisplayName(left)} leftVersion=${left.version} leftModel=${left.integrationModel}")
    Log.d("PiCheckDashboardUI", "rightName=${appDisplayName(right)} rightVersion=${right.version} rightModel=${right.integrationModel}")

    fun healthConnectColors() = ComparisonSideColors(PiCheckHealthConnect, PiCheckHealthConnectBg, PiCheckHealthConnect.copy(alpha = 0.35f), PiCheckHealthConnect)
    fun legacyColors() = ComparisonSideColors(PiCheckLegacy, PiCheckLegacyBg, PiCheckLegacy.copy(alpha = 0.35f), PiCheckLegacy)
    fun leftSideColors() = ComparisonSideColors(PiCheckCompareLeft, PiCheckCompareLeftBg, PiCheckCompareLeft.copy(alpha = 0.35f), if (leftIsHC) PiCheckHealthConnect else PiCheckModelLegacy)
    fun rightSideColors() = ComparisonSideColors(PiCheckCompareRight, PiCheckCompareRightBg, PiCheckCompareRight.copy(alpha = 0.35f), if (rightIsHC) PiCheckHealthConnect else PiCheckModelLegacy)

    return if (isEvolutionComparison) {
        Pair(if (leftIsHC) healthConnectColors() else legacyColors(), if (rightIsHC) healthConnectColors() else legacyColors())
    } else {
        Pair(leftSideColors(), rightSideColors())
    }
}

@Composable
private fun CompactComparisonHeader(left: DashboardSide, right: DashboardSide, leftColors: ComparisonSideColors, rightColors: ComparisonSideColors) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(bottom = 2.dp),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CompactSideSummary(left, leftColors, Modifier.weight(1f))
            Text("vs", color = PiCheckModelNeutral, fontWeight = FontWeight.ExtraBold)
            CompactSideSummary(right, rightColors, Modifier.weight(1f))
        }
    }
}

@Composable
private fun CompactSideSummary(side: DashboardSide, colors: ComparisonSideColors, modifier: Modifier = Modifier) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(4.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("${appDisplayName(side)} ${side.version?.let { "v$it" }.orEmpty()}", color = colors.accent, fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Row(horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
            ModelChip(modelDisplay(side.integrationModel), colors.modelColor, compact = true)
            Text("MobSF ${compactMobsfStatus(side.mobsfStatus)}", color = PiCheckModelNeutral, style = MaterialTheme.typography.labelSmall, maxLines = 1)
        }
    }
}

@Composable
private fun ModelChip(model: String, color: Color, compact: Boolean = false) {
    Text(
        text = if (compact) modelShort(model) else model,
        modifier = Modifier.clip(RoundedCornerShape(99.dp)).background(color.copy(alpha = 0.10f)).padding(horizontal = if (compact) 7.dp else 10.dp, vertical = if (compact) 2.dp else 4.dp),
        color = color,
        fontWeight = FontWeight.Bold,
        style = if (compact) MaterialTheme.typography.labelSmall else MaterialTheme.typography.bodySmall,
        maxLines = 1,
    )
}

@Composable
private fun MastgLegend() {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        LegendItem(MastgTestStatus.PASS, "Superada")
        LegendItem(MastgTestStatus.FAIL, "No superada")
        LegendItem(MastgTestStatus.REVIEW, "Revisión")
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        LegendItem(MastgTestStatus.NOT_EVALUABLE, "No evaluable")
        LegendItem(MastgTestStatus.ERROR, "Error")
    }
}

@Composable
private fun LegendItem(status: MastgTestStatus, label: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
        MastgStatusDot(status)
        Text(label, color = PiCheckModelNeutral, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun ComparisonTabSelector(selected: ComparisonTab, onSelected: (ComparisonTab) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(Color.White).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        listOf(ComparisonTab.GENERAL, ComparisonTab.MASTG).forEach { tab ->
            val active = tab == selected
            Text(
                text = if (tab == ComparisonTab.GENERAL) "General" else "Índice MASTG",
                modifier = Modifier.weight(1f).clip(RoundedCornerShape(14.dp)).background(if (active) PiCheckBlue else Color.Transparent).clickable { onSelected(tab) }.padding(vertical = 10.dp),
                color = if (active) Color.White else PiCheckDarkText,
                fontWeight = FontWeight.Bold,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
    }
}

@Composable
private fun GeneralTab(
    result: PiCheckComparisonAnalysis,
    dashboard: ComparisonDashboard?,
    left: DashboardSide,
    right: DashboardSide,
    leftColors: ComparisonSideColors,
    rightColors: ComparisonSideColors,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            ComparedAppCard(left, "Izquierda", leftColors, Modifier.weight(1f))
            ComparedAppCard(right, "Derecha", rightColors, Modifier.weight(1f))
        }
        if (!dashboard.hasDashboardValues()) DiagnosticCard()
        ExecutiveSummaryCard(dashboard?.executiveSummary.orEmpty())
        dashboard?.verdictCards.orEmpty().forEach { VerdictCard(it) }
        MetricSection("Evolución de plataforma", "targetSdk y minSdk declarados", dashboard?.platformMetrics.orEmpty(), sideDisplayName(left), sideDisplayName(right), leftColors.accent, rightColors.accent)
        MetricSection("Privacidad y permisos", "Permisos peligrosos, Health Connect, ubicación, almacenamiento y sensores", dashboard?.privacyMetrics.orEmpty(), sideDisplayName(left), sideDisplayName(right), leftColors.accent, rightColors.accent)
        MetricSection("Riesgos MobSF", "Hallazgos HIGH/WARNING y riesgos de manifest/código", dashboard?.securityMetrics.orEmpty(), sideDisplayName(left), sideDisplayName(right), leftColors.accent, rightColors.accent)
        MetricSection("Exposición externa", "Trackers, dominios y URLs", dashboard?.exposureMetrics.orEmpty(), sideDisplayName(left), sideDisplayName(right), leftColors.accent, rightColors.accent)
    }
}

@Composable
private fun ComparedAppCard(side: DashboardSide, sideLabel: String, colors: ComparisonSideColors, modifier: Modifier = Modifier) {
    val appName = appDisplayName(side)
    val model = modelDisplay(side.integrationModel)
    Card(modifier = modifier, shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, colors.border), colors = CardDefaults.cardColors(containerColor = colors.background)) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 12.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(sideLabel, color = colors.accent, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.labelMedium)
            AppIcon(side.icon, appName, colors.accent)
            Text(appName, color = colors.accent, fontWeight = FontWeight.ExtraBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text("Versión ${side.version ?: "N/D"}", color = PiCheckDarkText, fontWeight = FontWeight.SemiBold, maxLines = 1)
            ModelChip(model, colors.modelColor)
            Text("MobSF: ${side.mobsfStatus ?: "N/D"}", color = PiCheckModelNeutral, style = MaterialTheme.typography.bodySmall, maxLines = 1)
        }
    }
}

@Composable
private fun AppIcon(imageUrl: String?, fallback: String, color: Color) {
    Box(modifier = Modifier.size(58.dp).clip(CircleShape).background(color), contentAlignment = Alignment.Center) {
        Text(fallback.firstOrNull()?.uppercase() ?: "?", color = Color.White, fontWeight = FontWeight.ExtraBold)
        if (!imageUrl.isNullOrBlank()) AsyncImage(model = imageUrl, contentDescription = "Icono de $fallback", contentScale = ContentScale.Crop, modifier = Modifier.size(58.dp).clip(CircleShape))
    }
}

@Composable
private fun ExecutiveSummaryCard(summary: List<String>) {
    DashboardCard {
        Text("Resumen ejecutivo", color = PiCheckBlue, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        summary.ifEmpty { listOf("No hay resumen ejecutivo disponible para esta comparativa.") }.forEach { Text("• $it", color = PiCheckDarkText, style = MaterialTheme.typography.bodyMedium) }
    }
}

@Composable
private fun VerdictCard(card: DashboardVerdictCard) {
    DashboardCard {
        Text(card.title, color = PiCheckDarkText, fontWeight = FontWeight.ExtraBold)
        Text(card.summary ?: "Sin resumen disponible.", color = PiCheckDarkText.copy(alpha = 0.76f), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun MetricSection(
    title: String,
    subtitle: String? = null,
    metrics: List<DashboardMetric>,
    leftName: String,
    rightName: String,
    leftColor: Color,
    rightColor: Color,
    modifier: Modifier = Modifier,
) {
    DashboardCard(modifier) {
        Text(title, color = PiCheckBlue, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        subtitle?.let { Text(it, color = PiCheckModelNeutral, style = MaterialTheme.typography.bodySmall) }
        val visible = metrics.filter { it.leftValue != null || it.rightValue != null || !it.leftLabel.isNullOrBlank() || !it.rightLabel.isNullOrBlank() }
        if (visible.isEmpty()) {
            EmptyState("No hay métricas calculables para este bloque.")
        } else {
            visible.forEach { PureComposeBarChart(it, leftName, rightName, leftColor, rightColor) }
        }
    }
}

@Composable
private fun PureComposeBarChart(metric: DashboardMetric, leftName: String, rightName: String, leftColor: Color, rightColor: Color, modifier: Modifier = Modifier) {
    val maxValue = max(1f, max(metric.leftValue ?: 0f, metric.rightValue ?: 0f))
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(metric.label, color = PiCheckDarkText, fontWeight = FontWeight.Bold)
        BarRow(leftName, metric.leftLabel ?: valueLabel(metric.leftValue), metric.leftValue, maxValue, leftColor)
        BarRow(rightName, metric.rightLabel ?: valueLabel(metric.rightValue), metric.rightValue, maxValue, rightColor)
        Spacer(Modifier.height(4.dp))
    }
}

@Composable
private fun BarRow(title: String, valueLabel: String, value: Float?, maxValue: Float, color: Color) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, modifier = Modifier.width(88.dp), color = color, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Box(modifier = Modifier.weight(1f).height(12.dp).clip(RoundedCornerShape(99.dp)).background(PiCheckCardBorder)) {
            Box(modifier = Modifier.fillMaxWidth(((value ?: 0f) / maxValue).coerceIn(0f, 1f)).height(12.dp).clip(RoundedCornerShape(99.dp)).background(color))
        }
        Text(valueLabel, modifier = Modifier.width(62.dp), color = PiCheckDarkText, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun MastgIndexTab(dashboard: ComparisonDashboard?, leftName: String, rightName: String, leftColor: Color, rightColor: Color, leftColors: ComparisonSideColors, rightColors: ComparisonSideColors) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            MastgGauge(leftName, dashboard?.mastgScore?.left, leftColor, Modifier.weight(1f))
            MastgGauge(rightName, dashboard?.mastgScore?.right, rightColor, Modifier.weight(1f))
        }
        DashboardCard {
            Text("Evaluación preliminar basada en evidencias MobSF", color = PiCheckBlue, fontWeight = FontWeight.ExtraBold)
            Text(dashboard?.mastgScore?.label ?: "Evaluación MASTG pendiente", color = PiCheckDarkText.copy(alpha = 0.76f), style = MaterialTheme.typography.bodySmall)
        }
        MastgEvidenceTable(buildMastgRows(dashboard), leftName, rightName, leftColors.accent, rightColors.accent)
    }
}

@Composable
private fun MastgGauge(title: String, score: Float?, color: Color, modifier: Modifier = Modifier) {
    val boundedScore = score?.coerceIn(0f, 1f) ?: 0f
    val animatedScore by animateFloatAsState(targetValue = boundedScore, label = "mastg-gauge")
    DashboardCard(modifier) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Text(title, color = color, fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Box(contentAlignment = Alignment.Center) {
                Canvas(modifier = Modifier.size(112.dp)) {
                    val stroke = 13.dp.toPx(); val diameter = size.minDimension - stroke
                    val topLeft = Offset((size.width - diameter) / 2f, (size.height - diameter) / 2f)
                    val arcSize = Size(diameter, diameter)
                    drawArc(PiCheckCardBorder, 135f, 270f, false, topLeft, arcSize, Stroke(stroke, cap = StrokeCap.Round))
                    drawArc(if (score == null) PiCheckCardBorder else color, 135f, 270f * animatedScore, false, topLeft, arcSize, Stroke(stroke, cap = StrokeCap.Round))
                }
                Text(score?.let { "${(boundedScore * 100).toInt()}%" } ?: "Pendiente", color = if (score == null) PiCheckLegacyGray else color, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.bodySmall)
            }
            Text("Índice MASTG", color = PiCheckModelNeutral, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun MastgEvidenceTable(rows: List<MastgTestRow>, leftName: String, rightName: String, leftColor: Color, rightColor: Color) {
    DashboardCard {
        Text("Evidencias MobSF asociadas a MASTG", color = PiCheckBlue, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        MastgLegend()
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Prueba MASTG", Modifier.weight(1.8f), fontWeight = FontWeight.Bold, color = PiCheckDarkText)
            Text(leftName, Modifier.weight(1f), fontWeight = FontWeight.Bold, color = leftColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(rightName, Modifier.weight(1f), fontWeight = FontWeight.Bold, color = rightColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        rows.forEach { row ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1.8f)) { Text(row.title, color = PiCheckDarkText, fontWeight = FontWeight.SemiBold); Text(row.id, color = PiCheckModelNeutral, style = MaterialTheme.typography.labelSmall) }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) { MastgStatusDot(row.leftStatus) }
                Box(Modifier.weight(1f), contentAlignment = Alignment.Center) { MastgStatusDot(row.rightStatus) }
            }
        }
    }
}

@Composable
private fun MastgStatusDot(status: MastgTestStatus) {
    when (status) {
        MastgTestStatus.NOT_EVALUABLE -> Text("—", color = PiCheckLegacyGray, fontWeight = FontWeight.ExtraBold)
        MastgTestStatus.ERROR -> Text("✕", color = PiCheckRiskHigh, fontWeight = FontWeight.ExtraBold)
        else -> Box(Modifier.size(14.dp).clip(CircleShape).background(statusColor(status)))
    }
}

@Composable
private fun DashboardCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier = modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), border = BorderStroke(1.dp, PiCheckCardBorder), colors = CardDefaults.cardColors(containerColor = Color.White), elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
private fun DiagnosticCard() = EmptyState("No se han podido calcular métricas para el dashboard.\nRevisa Logcat con tag PiCheckDashboard.")

@Composable
private fun EmptyState(message: String) { Text(message, modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(PiCheckLegacyBg).padding(12.dp), color = PiCheckLegacyGray, style = MaterialTheme.typography.bodyMedium) }

private fun buildMastgRows(dashboard: ComparisonDashboard?): List<MastgTestRow> {
    fun metric(name: String) = (dashboard?.privacyMetrics.orEmpty() + dashboard?.securityMetrics.orEmpty() + dashboard?.exposureMetrics.orEmpty()).firstOrNull { it.label.contains(name, true) }
    fun failIfPositive(m: DashboardMetric?, left: Boolean, reviewOnNull: Boolean = false): MastgTestStatus {
        val v = if (left) m?.leftValue else m?.rightValue
        return when { v == null && reviewOnNull -> MastgTestStatus.REVIEW; v == null -> MastgTestStatus.PASS; v > 0f -> MastgTestStatus.FAIL; else -> MastgTestStatus.PASS }
    }
    fun reviewIfPositive(m: DashboardMetric?, left: Boolean, notEvaluableOnNull: Boolean = false): MastgTestStatus {
        val v = if (left) m?.leftValue else m?.rightValue
        return when { v == null && notEvaluableOnNull -> MastgTestStatus.NOT_EVALUABLE; v == null -> MastgTestStatus.PASS; v > 0f -> MastgTestStatus.REVIEW; else -> MastgTestStatus.PASS }
    }
    val dangerous = metric("peligros")
    val backup = metric("allowBackup")
    val clear = metric("Tráfico")
    val http = metric("URLs HTTP")
    val logging = metric("Logging")
    val external = metric("Almacenamiento externo")
    val trackers = metric("Trackers")
    return listOf(
        MastgTestRow("MASTG-TEST-0254", "Permisos peligrosos", "direct", failIfPositive(dangerous, true), failIfPositive(dangerous, false)),
        MastgTestRow("MASTG-TEST-0262", "Backup", "direct", failIfPositive(backup, true, true), failIfPositive(backup, false, true)),
        MastgTestRow("MASTG-TEST-0235", "Cleartext traffic", "direct", failIfPositive(clear, true), failIfPositive(clear, false)),
        MastgTestRow("MASTG-TEST-0233", "URLs HTTP", "direct/inferred", failIfPositive(http, true), failIfPositive(http, false)),
        MastgTestRow("MASTG-TEST-0231", "Logging", "inferred", reviewIfPositive(logging, true), reviewIfPositive(logging, false)),
        MastgTestRow("MASTG-TEST-0202", "Almacenamiento externo", "inferred", reviewIfPositive(external, true), reviewIfPositive(external, false)),
        MastgTestRow("MASTG-TEST-0206", "Exposición de PII en red", "inferred", reviewIfPositive(trackers, true, true), reviewIfPositive(trackers, false, true)),
        MastgTestRow("MASTG-TEST-0255", "Minimización de permisos", "inferred", reviewIfPositive(dangerous, true, true), reviewIfPositive(dangerous, false, true)),
    )
}

private fun ComparisonDashboard?.hasDashboardValues(): Boolean {
    if (this == null) return false
    val metrics = platformMetrics + privacyMetrics + securityMetrics + exposureMetrics
    return metrics.any { it.leftValue != null || it.rightValue != null || !it.leftLabel.isNullOrBlank() || !it.rightLabel.isNullOrBlank() }
}

private fun sideDisplayName(side: DashboardSide): String =
    listOfNotNull(appDisplayName(side), side.version?.let { "v$it" }).joinToString(" ")

private fun appDisplayName(side: DashboardSide): String {
    val candidates = listOf(side.name, side.appName, side.title, side.label, side.appId)
    return candidates.firstOrNull { value ->
        !value.isNullOrBlank() && !value.isIntegrationModelLabel()
    } ?: side.appId ?: "Aplicación"
}

private fun String.isIntegrationModelLabel(): Boolean =
    equals("Health Connect", ignoreCase = true) ||
            equals("Legacy", ignoreCase = true) ||
            equals("HEALTH_CONNECT", ignoreCase = true) ||
            equals("health_connect", ignoreCase = true) ||
            equals("HC", ignoreCase = true) ||
            equals("L", ignoreCase = true)

private fun valueLabel(value: Float?): String = when { value == null -> "N/D"; value % 1f == 0f -> value.toInt().toString(); else -> "%.1f".format(value) }
private fun modelDisplay(value: String?): String = if (isHealthConnectModel(value)) "Health Connect" else if (isLegacyModel(value)) "Legacy" else value ?: "Modelo desconocido"
private fun modelShort(value: String): String = when { value.contains("health", true) -> "HC"; value.contains("legacy", true) -> "Legacy"; else -> value.take(8) }
private fun isHealthConnectModel(value: String?): Boolean = value.equals("HEALTH_CONNECT", true) || value.equals("health_connect", true) || value.equals("Health Connect", true)
private fun isLegacyModel(value: String?): Boolean = value.equals("LEGACY", true) || value.equals("legacy", true) || value.equals("Legacy", true)
private fun compactMobsfStatus(value: String?): String = when (value?.lowercase()) { "success", "ok", "completed" -> "OK"; "error", "failed" -> "ERROR"; "pending", "queued", "running" -> "PENDING"; else -> value ?: "N/D" }
private fun statusColor(status: MastgTestStatus): Color = when (status) { MastgTestStatus.PASS -> PiCheckSuccess; MastgTestStatus.FAIL -> PiCheckRiskHigh; MastgTestStatus.REVIEW -> PiCheckWarning; MastgTestStatus.NOT_EVALUABLE -> PiCheckLegacyGray; MastgTestStatus.ERROR -> PiCheckRiskHigh }
