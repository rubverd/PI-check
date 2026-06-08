package es.uva.picheck.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.data.model.PiCheckVersionReport
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComparisonResultScreen(
    result: PiCheckComparisonAnalysis,
    onNewComparison: () -> Unit,
) {
    var showFullJson by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Resultado de la comparativa",
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
                SummaryCard(result = result)
            }

            item {
                VersionReportCard(
                    title = "Aplicación A",
                    report = result.appA,
                )
            }

            item {
                VersionReportCard(
                    title = "Aplicación B",
                    report = result.appB,
                )
            }

            item {
                MessagesCard(messages = result.messages)
            }

            item {
                JsonPreviewCard(
                    title = "JSON devuelto por el backend",
                    json = result.rawJson,
                    expanded = showFullJson,
                    onToggle = {
                        showFullJson = !showFullJson
                    },
                )
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
private fun SummaryCard(result: PiCheckComparisonAnalysis) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "Comparativa generada",
                style = MaterialTheme.typography.titleMedium,
                color = PiCheckBlue,
                fontWeight = FontWeight.Bold,
            )

            InfoLine(label = "ID", value = result.comparisonId)
            InfoLine(label = "Estado", value = result.status)
            InfoLine(label = "Mensaje", value = result.message)
            InfoLine(
                label = "Índice aplicado",
                value = result.idIndiceAplicado ?: "No aplicado todavía",
            )
        }
    }
}

@Composable
private fun VersionReportCard(
    title: String,
    report: PiCheckVersionReport,
) {
    val versionApp = report.versionApp
    val mobsfReport = report.mobsfReport

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = PiCheckBurgundy,
                fontWeight = FontWeight.Bold,
            )

            InfoLine(label = "Paquete", value = versionApp.idApp)
            InfoLine(label = "Versión", value = versionApp.version)
            InfoLine(label = "Version code", value = versionApp.versionCode?.toString() ?: "No disponible")
            InfoLine(label = "Fecha versión", value = versionApp.fechaVersion ?: "No disponible")
            InfoLine(label = "Categoría", value = versionApp.categoria ?: "No disponible")
            InfoLine(label = "Modelo integración", value = versionApp.modeloIntegracion)
            InfoLine(label = "Estado MobSF", value = versionApp.estadoMobsf)
            InfoLine(label = "Hash APK", value = versionApp.apkSha256 ?: "No disponible")
            InfoLine(label = "Hash MobSF", value = versionApp.hashMobsf ?: "No disponible")
            InfoLine(label = "Ruta informe", value = versionApp.rutaInformeMobsf ?: "No disponible")

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = if (mobsfReport.available) {
                    "Informe MobSF disponible"
                } else {
                    "Informe MobSF no disponible"
                },
                color = if (mobsfReport.available) PiCheckBlue else PiCheckBurgundy,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyMedium,
            )

            if (mobsfReport.available) {
                InfoLine(label = "Archivo", value = mobsfReport.fileName ?: "No disponible")
                InfoLine(label = "Tipo análisis", value = mobsfReport.scanType ?: "No disponible")
                InfoLine(label = "Ruta JSON", value = mobsfReport.rutaInforme ?: "No disponible")
            }
        }
    }
}

@Composable
private fun MessagesCard(messages: List<String>) {
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
}

@Composable
private fun JsonPreviewCard(
    title: String,
    json: String,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    val visibleJson = if (expanded) {
        json
    } else {
        json.take(3000) + if (json.length > 3000) "\n\n... JSON truncado en vista previa ..." else ""
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
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
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
    }
}