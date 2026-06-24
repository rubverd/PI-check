package es.uva.picheck.ui.screens

import android.util.Log
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.BorderStroke
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
import es.uva.picheck.ui.theme.PiCheckDarkText
import es.uva.picheck.ui.theme.PiCheckLegacyBg
import es.uva.picheck.ui.theme.PiCheckLegacyGray
import es.uva.picheck.ui.theme.PiCheckModelLegacy
import es.uva.picheck.ui.theme.PiCheckModelNeutral
import kotlin.math.max

private enum class ComparisonTab { GENERAL, MASTG }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComparisonResultScreen(result: PiCheckComparisonAnalysis, onNewComparison: () -> Unit) {
    val dashboard = result.dashboard
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
            item { ComparisonTabSelector(selectedTab) { selectedTab = it } }
            item {
                Crossfade(targetState = selectedTab, label = "comparison-tab") { tab ->
                    when (tab) {
                        ComparisonTab.GENERAL -> GeneralTab(result, dashboard)
                        ComparisonTab.MASTG -> MastgIndexTab(
                            dashboard = dashboard,
                            leftName = sideDisplayName(dashboard, true),
                            rightName = sideDisplayName(dashboard, false),
                            leftColor = PiCheckCompareLeft,
                            rightColor = PiCheckCompareRight,
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
private fun GeneralTab(result: PiCheckComparisonAnalysis, dashboard: ComparisonDashboard?) {
    val left = dashboard?.header?.left ?: DashboardSide(label = result.appA.versionApp.idApp, version = result.appA.versionApp.version, integrationModel = result.appA.versionApp.modeloIntegracion, mobsfStatus = result.appA.versionApp.estadoMobsf)
    val right = dashboard?.header?.right ?: DashboardSide(label = result.appB.versionApp.idApp, version = result.appB.versionApp.version, integrationModel = result.appB.versionApp.modeloIntegracion, mobsfStatus = result.appB.versionApp.estadoMobsf)
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            ComparedAppCard(left, "Izquierda", PiCheckCompareLeft, PiCheckCompareLeftBg, Modifier.weight(1f))
            ComparedAppCard(right, "Derecha", PiCheckCompareRight, PiCheckCompareRightBg, Modifier.weight(1f))
        }
        if (!dashboard.hasDashboardValues()) DiagnosticCard()
        ExecutiveSummaryCard(dashboard?.executiveSummary.orEmpty())
        dashboard?.verdictCards.orEmpty().forEach { VerdictCard(it) }
        MetricSection("Evolución de plataforma", "targetSdk y minSdk declarados", dashboard?.platformMetrics.orEmpty(), sideDisplayName(dashboard, true), sideDisplayName(dashboard, false))
        MetricSection("Privacidad y permisos", "Permisos peligrosos, Health Connect, ubicación, almacenamiento y sensores", dashboard?.privacyMetrics.orEmpty(), sideDisplayName(dashboard, true), sideDisplayName(dashboard, false))
        MetricSection("Riesgos MobSF", "Hallazgos HIGH/WARNING y riesgos de manifest/código", dashboard?.securityMetrics.orEmpty(), sideDisplayName(dashboard, true), sideDisplayName(dashboard, false))
        MetricSection("Exposición externa", "Trackers, dominios y URLs", dashboard?.exposureMetrics.orEmpty(), sideDisplayName(dashboard, true), sideDisplayName(dashboard, false))
    }
}

@Composable
private fun ComparedAppCard(side: DashboardSide, sideLabel: String, sideColor: Color, sideBackground: Color, modifier: Modifier = Modifier) {
    val model = modelDisplay(side.integrationModel ?: side.label)
    val modelColor = if (isHealthConnect(model)) sideColor else PiCheckModelLegacy
    Card(modifier = modifier, shape = RoundedCornerShape(20.dp), border = BorderStroke(1.dp, sideColor.copy(alpha = 0.35f)), colors = CardDefaults.cardColors(containerColor = sideBackground)) {
        Column(modifier = Modifier.padding(14.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(sideLabel, color = sideColor, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.labelMedium)
            AppIcon(side.icon, side.label ?: side.appId ?: sideLabel, sideColor)
            Text(side.label ?: side.appId ?: "Aplicación", color = sideColor, fontWeight = FontWeight.ExtraBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text("Versión ${side.version ?: "N/D"}", color = PiCheckDarkText, fontWeight = FontWeight.SemiBold, maxLines = 1)
            Text(model, modifier = Modifier.clip(RoundedCornerShape(99.dp)).background(Color.White.copy(alpha = 0.85f)).padding(horizontal = 10.dp, vertical = 4.dp), color = modelColor, fontWeight = FontWeight.Bold, maxLines = 1)
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
private fun MetricSection(title: String, subtitle: String? = null, metrics: List<DashboardMetric>, leftName: String, rightName: String, modifier: Modifier = Modifier) {
    DashboardCard(modifier) {
        Text(title, color = PiCheckBlue, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        subtitle?.let { Text(it, color = PiCheckModelNeutral, style = MaterialTheme.typography.bodySmall) }
        val visible = metrics.filter { it.leftValue != null || it.rightValue != null || !it.leftLabel.isNullOrBlank() || !it.rightLabel.isNullOrBlank() }
        if (visible.isEmpty()) EmptyState("No hay métricas calculables para este bloque.") else visible.forEach { PureComposeBarChart(it, leftName, rightName, PiCheckCompareLeft, PiCheckCompareRight) }
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
private fun MastgIndexTab(dashboard: ComparisonDashboard?, leftName: String, rightName: String, leftColor: Color, rightColor: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            MastgGauge(leftName, dashboard?.mastgScore?.left, leftColor, Modifier.weight(1f))
            MastgGauge(rightName, dashboard?.mastgScore?.right, rightColor, Modifier.weight(1f))
        }
        DashboardCard {
            Text("Evaluación preliminar basada en evidencias MobSF", color = PiCheckBlue, fontWeight = FontWeight.ExtraBold)
            Text(dashboard?.mastgScore?.label ?: "Evaluación MASTG pendiente", color = PiCheckDarkText.copy(alpha = 0.76f), style = MaterialTheme.typography.bodySmall)
        }
        MastgEvidenceTable(buildMastgRows(dashboard), leftName, rightName)
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
private fun MastgEvidenceTable(rows: List<MastgTestRow>, leftName: String, rightName: String) {
    DashboardCard {
        Text("Tabla de pruebas MASTG", color = PiCheckBlue, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Prueba MASTG", Modifier.weight(1.8f), fontWeight = FontWeight.Bold, color = PiCheckDarkText)
            Text(leftName, Modifier.weight(1f), fontWeight = FontWeight.Bold, color = PiCheckCompareLeft, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(rightName, Modifier.weight(1f), fontWeight = FontWeight.Bold, color = PiCheckCompareRight, maxLines = 1, overflow = TextOverflow.Ellipsis)
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
        MastgTestStatus.ERROR -> Text("X", color = PiCheckBurgundy, fontWeight = FontWeight.ExtraBold)
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

private fun sideDisplayName(dashboard: ComparisonDashboard?, left: Boolean): String {
    val side = if (left) dashboard?.header?.left else dashboard?.header?.right
    return listOfNotNull(side?.label, side?.version?.let { "v$it" }).joinToString(" ").ifBlank { if (left) "Izquierda" else "Derecha" }
}

private fun valueLabel(value: Float?): String = when { value == null -> "N/D"; value % 1f == 0f -> value.toInt().toString(); else -> "%.1f".format(value) }
private fun modelDisplay(value: String?): String = if (value?.contains("health", true) == true) "Health Connect" else if (value?.contains("legacy", true) == true) "Legacy" else value ?: "Modelo desconocido"
private fun isHealthConnect(value: String): Boolean = value.contains("Health Connect", true) || value.contains("HEALTH_CONNECT", true) || value.contains("health_connect", true)
private fun statusColor(status: MastgTestStatus): Color = when (status) { MastgTestStatus.PASS -> Color(0xFF16A34A); MastgTestStatus.FAIL -> Color(0xFFDC2626); MastgTestStatus.REVIEW -> Color(0xFFEAB308); MastgTestStatus.NOT_EVALUABLE -> PiCheckLegacyGray; MastgTestStatus.ERROR -> PiCheckBurgundy }
