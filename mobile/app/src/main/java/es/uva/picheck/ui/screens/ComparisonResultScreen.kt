package es.uva.picheck.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import es.uva.picheck.data.model.ComparisonDashboard
import es.uva.picheck.data.model.DashboardVerdictCard
import es.uva.picheck.data.model.DashboardHeader
import es.uva.picheck.data.model.DashboardMetric
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.data.model.QuickKpi
import es.uva.picheck.data.model.TechnicalFinding
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import es.uva.picheck.ui.theme.PiCheckHCBlue
import es.uva.picheck.ui.theme.PiCheckHCGreen
import es.uva.picheck.ui.theme.PiCheckHCHint
import es.uva.picheck.ui.theme.PiCheckLegacyBg
import es.uva.picheck.ui.theme.PiCheckLegacyDark
import es.uva.picheck.ui.theme.PiCheckLegacyGray
import kotlin.math.max

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComparisonResultScreen(
    result: PiCheckComparisonAnalysis,
    onNewComparison: () -> Unit,
) {
    var selectedTab by remember { mutableStateOf(0) }
    val dashboard = result.dashboard
    val tabs = listOf("Resumen", "Privacidad", "Seguridad", "Exposición", "Técnico")

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Dashboard de comparativa",
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PiCheckBurgundy,
                ),
            )
        },
        containerColor = PiCheckBackground,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .padding(innerPadding)
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                ComparisonHeaderCard(
                    header = dashboard?.header,
                    fallback = result,
                )
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    MastgGauge(
                        title = dashboard?.header?.leftTitle ?: "Izquierda",
                        score = dashboard?.mastgScore?.left,
                        modifier = Modifier.weight(1f),
                    )
                    MastgGauge(
                        title = dashboard?.header?.rightTitle ?: "Derecha",
                        score = dashboard?.mastgScore?.right,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            item {
                ExecutiveSummaryCard(dashboard?.executiveSummary.orEmpty())
            }

            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(18.dp),
                    border = BorderStroke(1.dp, PiCheckCardBorder),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        TabRow(
                            selectedTabIndex = selectedTab,
                            containerColor = Color.White,
                            contentColor = PiCheckBlue,
                        ) {
                            tabs.forEachIndexed { index, title ->
                                Tab(
                                    selected = selectedTab == index,
                                    onClick = { selectedTab = index },
                                    text = {
                                        Text(
                                            text = title,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    },
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        when (selectedTab) {
                            0 -> SummaryTab(dashboard)
                            1 -> PrivacyTab(dashboard)
                            2 -> SecurityTab(dashboard)
                            3 -> MetricsSection(
                                title = "Exposición externa",
                                metrics = dashboard?.exposureMetrics.orEmpty(),
                                emptyMessage = "No hay métricas de exposición disponibles.",
                            )
                            else -> TechnicalTab(result)
                        }
                    }
                }
            }

            item {
                Button(
                    onClick = onNewComparison,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBlue,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = "Realizar nueva comparativa",
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

@Composable
private fun ComparisonHeaderCard(
    header: DashboardHeader?,
    fallback: PiCheckComparisonAnalysis,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = header?.appName ?: "Comparativa generada",
                color = PiCheckBlue,
                fontWeight = FontWeight.ExtraBold,
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                text = fallback.message,
                color = PiCheckDarkText.copy(alpha = 0.76f),
                style = MaterialTheme.typography.bodySmall,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                HeaderSide(
                    title = header?.left?.label ?: header?.leftTitle ?: "Aplicación A",
                    version = header?.left?.version ?: header?.leftVersion ?: fallback.appA.versionApp.version,
                    integrationModel = header?.left?.integrationModel ?: header?.leftIntegrationModel ?: fallback.appA.versionApp.modeloIntegracion,
                    mobsfStatus = header?.left?.mobsfStatus ?: header?.leftMobsfStatus ?: fallback.appA.versionApp.estadoMobsf,
                    icon = header?.left?.icon ?: header?.leftIcon,
                    isHealthConnect = isHealthConnect(header?.left?.integrationModel ?: header?.leftIntegrationModel ?: fallback.appA.versionApp.modeloIntegracion),
                    modifier = Modifier.weight(1f),
                )
                HeaderSide(
                    title = header?.right?.label ?: header?.rightTitle ?: "Aplicación B",
                    version = header?.right?.version ?: header?.rightVersion ?: fallback.appB.versionApp.version,
                    integrationModel = header?.right?.integrationModel ?: header?.rightIntegrationModel ?: fallback.appB.versionApp.modeloIntegracion,
                    mobsfStatus = header?.right?.mobsfStatus ?: header?.rightMobsfStatus ?: fallback.appB.versionApp.estadoMobsf,
                    icon = header?.right?.icon ?: header?.rightIcon,
                    isHealthConnect = isHealthConnect(header?.right?.integrationModel ?: header?.rightIntegrationModel ?: fallback.appB.versionApp.modeloIntegracion),
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun HeaderSide(
    title: String,
    version: String,
    integrationModel: String,
    mobsfStatus: String,
    icon: String?,
    isHealthConnect: Boolean,
    modifier: Modifier = Modifier,
) {
    val background = if (isHealthConnect) PiCheckHCHint else PiCheckLegacyBg
    val accent = if (isHealthConnect) PiCheckHCBlue else PiCheckLegacyDark

    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(background)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        AppIcon(imageUrl = icon, fallback = title)
        Text(
            text = title,
            color = accent,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = "v$version",
            color = PiCheckDarkText,
            fontWeight = FontWeight.SemiBold,
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            text = integrationModel,
            color = PiCheckDarkText.copy(alpha = 0.72f),
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            text = "MobSF: $mobsfStatus",
            color = PiCheckDarkText.copy(alpha = 0.72f),
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun AppIcon(
    imageUrl: String?,
    fallback: String,
) {
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .background(PiCheckBlue),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = fallback.firstOrNull()?.uppercase() ?: "?",
            color = Color.White,
            fontWeight = FontWeight.Bold,
        )
        if (!imageUrl.isNullOrBlank()) {
            AsyncImage(
                model = imageUrl,
                contentDescription = "Icono de $fallback",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape),
            )
        }
    }
}

@Composable
private fun MastgGauge(
    title: String,
    score: Float?,
    modifier: Modifier = Modifier,
) {
    val boundedScore = score?.coerceIn(0f, 1f) ?: 0f
    val animatedScore by animateFloatAsState(
        targetValue = boundedScore,
        label = "mastg-gauge",
    )

    Card(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = title,
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Box(contentAlignment = Alignment.Center) {
                Canvas(modifier = Modifier.size(104.dp)) {
                    val stroke = 13.dp.toPx()
                    val diameter = size.minDimension - stroke
                    val topLeft = Offset(
                        x = (size.width - diameter) / 2f,
                        y = (size.height - diameter) / 2f,
                    )
                    val arcSize = Size(diameter, diameter)
                    drawArc(
                        color = PiCheckCardBorder,
                        startAngle = 135f,
                        sweepAngle = 270f,
                        useCenter = false,
                        topLeft = topLeft,
                        size = arcSize,
                        style = Stroke(width = stroke, cap = StrokeCap.Round),
                    )
                    drawArc(
                        color = if (score == null) PiCheckLegacyGray else PiCheckHCGreen,
                        startAngle = 135f,
                        sweepAngle = 270f * animatedScore,
                        useCenter = false,
                        topLeft = topLeft,
                        size = arcSize,
                        style = Stroke(width = stroke, cap = StrokeCap.Round),
                    )
                }
                Text(
                    text = score?.let { "${(boundedScore * 100).toInt()}%" } ?: "PENDIENTE",
                    color = if (score == null) PiCheckLegacyGray else PiCheckBlue,
                    fontWeight = FontWeight.ExtraBold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(
                text = "Índice MASTG",
                color = PiCheckDarkText.copy(alpha = 0.65f),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ExecutiveSummaryCard(summary: List<String>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Resumen ejecutivo",
                color = PiCheckBlue,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
            )
            val lines = summary.ifEmpty {
                listOf("No hay resumen ejecutivo disponible; consulta la pestaña Técnico para ver el JSON bruto.")
            }
            lines.forEach { line ->
                Text(
                    text = "• $line",
                    color = PiCheckDarkText,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun SummaryTab(dashboard: ComparisonDashboard?) {
    val verdictCards = dashboard?.verdictCards.orEmpty()
    val fallbackKpis = dashboard?.quickKpis.orEmpty()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (verdictCards.isEmpty() && fallbackKpis.isEmpty()) {
            EmptyState("No hay métricas resumidas disponibles.")
        } else {
            verdictCards.forEach { card -> VerdictCard(card) }
            fallbackKpis.forEach { kpi -> QuickKpiCard(kpi) }
        }

        MetricsSection(
            title = "Plataforma Android",
            metrics = dashboard?.platformMetrics.orEmpty(),
            emptyMessage = "No hay métricas de plataforma disponibles.",
        )
    }
}

@Composable
private fun VerdictCard(card: DashboardVerdictCard) {
    val accent = when (card.status?.lowercase()) {
        "positive" -> PiCheckHCGreen
        "warning" -> Color(0xFFE09000)
        "risk" -> PiCheckBurgundy
        else -> PiCheckLegacyGray
    }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFBFCFF)),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = card.title,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = winnerLabel(card.winner),
                    color = accent,
                    fontWeight = FontWeight.ExtraBold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(
                text = card.summary ?: "Sin resumen disponible.",
                color = PiCheckDarkText.copy(alpha = 0.78f),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun QuickKpiCard(kpi: QuickKpi) {
    val accent = when (kpi.level?.lowercase()) {
        "positive" -> PiCheckHCGreen
        "risk" -> PiCheckBurgundy
        else -> PiCheckHCBlue
    }
    val status = when (kpi.winner?.lowercase()) {
        "left", "right" -> "Mejora"
        "risk" -> "Riesgo"
        else -> "Revisión"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFBFCFF)),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = kpi.title,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = status,
                    color = accent,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                KpiValueBox("Izquierda", kpi.leftLabel ?: valueLabel(kpi.leftValue), PiCheckHCBlue, Modifier.weight(1f))
                KpiValueBox("Derecha", kpi.rightLabel ?: valueLabel(kpi.rightValue), PiCheckLegacyDark, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun KpiValueBox(
    title: String,
    value: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(color.copy(alpha = 0.08f))
            .padding(10.dp),
    ) {
        Text(
            text = title,
            color = color,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.bodySmall,
        )
        Text(
            text = value,
            color = PiCheckDarkText,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun PrivacyTab(dashboard: ComparisonDashboard?) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            text = "Health Connect puede aumentar el número de permisos declarados, pero introduce permisos más granulares para datos de salud.",
            color = PiCheckDarkText.copy(alpha = 0.78f),
            style = MaterialTheme.typography.bodySmall,
        )
        MetricsSection(
            title = "Privacidad y permisos",
            metrics = dashboard?.privacyMetrics.orEmpty(),
            emptyMessage = "No hay métricas de privacidad disponibles.",
        )
        dashboard?.permissionDiff?.let { diff ->
            PermissionDiffCard(
                added = diff.addedInLeft,
                removed = diff.removedInLeft,
                healthConnect = diff.healthConnectPermissions,
            )
        }
    }
}

@Composable
private fun PermissionDiffCard(
    added: List<String>,
    removed: List<String>,
    healthConnect: List<String>,
) {
    var expanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFBFCFF)),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "Diferencia de permisos",
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Añadidos: ${added.size} · Eliminados: ${removed.size} · Health Connect: ${healthConnect.size}",
                color = PiCheckDarkText.copy(alpha = 0.72f),
                style = MaterialTheme.typography.bodySmall,
            )
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    PermissionList("Añadidos en izquierda", added)
                    PermissionList("Eliminados en izquierda", removed)
                    PermissionList("Permisos Health Connect", healthConnect)
                }
            }
        }
    }
}

@Composable
private fun PermissionList(title: String, values: List<String>) {
    Text(
        text = "$title: ${values.take(8).joinToString().ifBlank { "N/D" }}",
        color = PiCheckDarkText,
        style = MaterialTheme.typography.bodySmall,
        maxLines = 4,
        overflow = TextOverflow.Ellipsis,
    )
}

@Composable
private fun MetricsSection(
    title: String,
    metrics: List<DashboardMetric>,
    emptyMessage: String,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            text = title,
            color = PiCheckBlue,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
        )
        if (metrics.isEmpty()) {
            EmptyState(emptyMessage)
        } else {
            metrics.forEach { metric ->
                ComparisonBarMetric(
                    label = metric.label,
                    leftLabel = metric.leftLabel ?: valueLabel(metric.leftValue),
                    rightLabel = metric.rightLabel ?: valueLabel(metric.rightValue),
                    leftValue = metric.leftValue,
                    rightValue = metric.rightValue,
                    preferred = metric.preferred,
                )
            }
        }
    }
}

@Composable
private fun ComparisonBarMetric(
    label: String,
    leftLabel: String,
    rightLabel: String,
    leftValue: Float?,
    rightValue: Float?,
    preferred: String?,
) {
    val maxValue = max(1f, max(leftValue ?: 0f, rightValue ?: 0f))
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = label,
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = preferredLabel(preferred),
                color = PiCheckLegacyGray,
                style = MaterialTheme.typography.bodySmall,
            )
        }
        BarRow("Izquierda", leftLabel, leftValue, maxValue, PiCheckHCBlue)
        BarRow("Derecha", rightLabel, rightValue, maxValue, PiCheckLegacyGray)
    }
}

@Composable
private fun BarRow(
    title: String,
    valueLabel: String,
    value: Float?,
    maxValue: Float,
    color: Color,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = title,
            modifier = Modifier.width(72.dp),
            color = PiCheckDarkText.copy(alpha = 0.72f),
            style = MaterialTheme.typography.bodySmall,
        )
        Box(
            modifier = Modifier
                .weight(1f)
                .height(12.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(PiCheckCardBorder),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(((value ?: 0f) / maxValue).coerceIn(0f, 1f))
                    .height(12.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(color),
            )
        }
        Text(
            text = valueLabel,
            modifier = Modifier.width(72.dp),
            color = PiCheckDarkText,
            fontWeight = FontWeight.SemiBold,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun SecurityTab(dashboard: ComparisonDashboard?) {
    val metrics = dashboard?.securityMetrics.orEmpty()
    val findings = dashboard?.technicalFindings.orEmpty()
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (metrics.isEmpty()) {
            EmptyState("No hay métricas de seguridad agregadas disponibles.")
        } else {
            metrics.forEach { metric ->
                ComparisonBarMetric(
                    label = metric.label,
                    leftLabel = metric.leftLabel ?: valueLabel(metric.leftValue),
                    rightLabel = metric.rightLabel ?: valueLabel(metric.rightValue),
                    leftValue = metric.leftValue,
                    rightValue = metric.rightValue,
                    preferred = metric.preferred,
                )
            }
        }

        Text(
            text = "Hallazgos técnicos",
            color = PiCheckBlue,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
        )
        if (findings.isEmpty()) {
            EmptyState("No hay hallazgos técnicos resumidos disponibles.")
        } else {
            findings.forEach { finding -> ExpandableFindingCard(finding) }
        }
    }
}

@Composable
private fun ExpandableFindingCard(finding: TechnicalFinding) {
    var expanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFBFCFF)),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = finding.title,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = finding.severity ?: "INFO",
                    color = severityColor(finding.severity),
                    fontWeight = FontWeight.ExtraBold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Text(
                text = "Afecta a: ${sideLabel(finding.affectedSide)}",
                color = PiCheckDarkText.copy(alpha = 0.72f),
                style = MaterialTheme.typography.bodySmall,
            )
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    finding.summary?.let { InfoLine("Resumen", it) }
                    finding.description?.let { InfoLine("Descripción", it) }
                    finding.category?.let { InfoLine("Categoría", it) }
                    finding.mastgRelation?.let { InfoLine("Relación MASTG", it) }
                    finding.relationType?.let { InfoLine("Tipo relación", it) }
                    finding.detail?.let { InfoLine("Detalle", it) }
                    finding.masvs?.let { InfoLine("MASVS", it) }
                    finding.cwe?.let { InfoLine("CWE", it) }
                }
            }
        }
    }
}

@Composable
private fun TechnicalTab(result: PiCheckComparisonAnalysis) {
    var showFullJson by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        InfoLine("Artefacto temporal", result.comparisonArtifactPath ?: "No generado")
        InfoLine("ID", result.comparisonId)
        result.dashboard?.technicalSummary?.let { summary ->
            InfoLine("Informe izquierdo", reportSummary(summary.leftReportAvailable, summary.leftReportSizeBytes))
            InfoLine("Informe derecho", reportSummary(summary.rightReportAvailable, summary.rightReportSizeBytes))
            InfoLine("Raw MobSF en respuesta", if (summary.rawReportInResponse == true) "Sí" else "No")
        }
        JsonPreviewCard(
            title = "JSON resumido del dashboard",
            json = result.comparisonJson ?: result.rawJson,
            expanded = showFullJson,
            onToggle = { showFullJson = !showFullJson },
        )
        MessagesCard(messages = result.messages)
    }
}

@Composable
private fun MessagesCard(messages: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = "Trazabilidad del proceso",
            color = PiCheckBlue,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
        )
        messages.forEachIndexed { index, message ->
            Text(
                text = "${index + 1}. $message",
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun JsonPreviewCard(
    title: String,
    json: String,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    val maxJsonChars = 50 * 1024
    val sourceJson = if (json.length > maxJsonChars) {
        json.take(maxJsonChars) + "\n\n... contenido truncado para proteger la UI ..."
    } else {
        json
    }
    val visibleJson = if (expanded) {
        sourceJson
    } else {
        sourceJson.take(3000) + if (sourceJson.length > 3000) "\n\n... JSON truncado en vista previa ..." else ""
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = title,
            color = PiCheckBlue,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
        )

        OutlinedButton(
            onClick = onToggle,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                text = if (expanded) "Mostrar vista previa" else "Mostrar JSON completo",
            )
        }

        SelectionContainer {
            Text(
                text = visibleJson,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                color = PiCheckDarkText,
                fontFamily = FontFamily.Monospace,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun EmptyState(message: String) {
    Text(
        text = message,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(PiCheckLegacyBg)
            .padding(12.dp),
        color = PiCheckLegacyGray,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun InfoLine(
    label: String,
    value: String,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            text = "$label: ",
            color = PiCheckDarkText,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.bodySmall,
        )

        Text(
            text = value,
            color = PiCheckDarkText,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 4,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

private fun valueLabel(value: Float?): String = when {
    value == null -> "N/D"
    value % 1f == 0f -> value.toInt().toString()
    else -> "%.1f".format(value)
}

private fun winnerLabel(value: String?): String = when (value?.lowercase()) {
    "left" -> "HC"
    "right" -> "Legacy"
    "tie" -> "Empate"
    "pending" -> "Pendiente"
    else -> "Revisión"
}

private fun preferredLabel(value: String?): String = when (value?.lowercase()) {
    "higher" -> "mayor es mejor"
    "lower" -> "menor es mejor"
    "context" -> "contexto"
    else -> "comparativo"
}

private fun reportSummary(available: Boolean?, sizeBytes: Long?): String {
    val availability = if (available == true) "disponible" else "no disponible"
    val size = sizeBytes?.let { " · ${it / 1024} KB" }.orEmpty()
    return availability + size
}

private fun sideLabel(value: String?): String = when (value?.lowercase()) {
    "left" -> "Izquierda"
    "right" -> "Derecha"
    else -> "No especificado"
}

private fun severityColor(value: String?): Color = when (value?.lowercase()) {
    "high", "critical" -> PiCheckBurgundy
    "warning", "medium" -> Color(0xFFE09000)
    else -> PiCheckLegacyGray
}

private fun isHealthConnect(value: String): Boolean =
    value.equals("HEALTH_CONNECT", ignoreCase = true) ||
        value.equals("health_connect", ignoreCase = true)
