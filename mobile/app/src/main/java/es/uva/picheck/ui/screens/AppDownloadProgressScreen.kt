package es.uva.picheck.ui.screens

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.remote.PiCheckApiClient
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppDownloadProgressScreen(
    appA: PlayStoreApp,
    appB: PlayStoreApp,
    onFinished: (PiCheckComparisonAnalysis) -> Unit,
    onBack: () -> Unit,
) {
    var progress by remember { mutableFloatStateOf(0.05f) }
    var animationStep by remember { mutableIntStateOf(0) }

    var isFinished by remember { mutableStateOf(false) }
    var hasError by remember { mutableStateOf(false) }

    var statusMessage by remember { mutableStateOf("Preparando solicitud de comparación...") }
    var detailMessage by remember {
        mutableStateOf("Comprobando metadatos y preparando análisis.")
    }

    val animatedProgress by animateFloatAsState(
        targetValue = progress.coerceIn(0f, 1f),
        animationSpec = tween(durationMillis = 700),
        label = "download_progress",
    )

    LaunchedEffect(isFinished, hasError) {
        if (!isFinished && !hasError) {
            while (true) {
                delay(1200)
                animationStep = (animationStep + 1) % 3
            }
        }
    }

    LaunchedEffect(Unit) {
        val progressJob = launch {
            while (!isFinished && progress < 0.90f) {
                delay(1400)

                progress = when {
                    progress < 0.20f -> (progress + 0.040f).coerceAtMost(0.20f)
                    progress < 0.42f -> (progress + 0.035f).coerceAtMost(0.42f)
                    progress < 0.65f -> (progress + 0.025f).coerceAtMost(0.65f)
                    progress < 0.82f -> (progress + 0.018f).coerceAtMost(0.82f)
                    else -> (progress + 0.010f).coerceAtMost(0.90f)
                }

                statusMessage = when {
                    progress < 0.20f -> "Registrando solicitud de comparación..."
                    progress < 0.42f -> "Comprobando análisis previos..."
                    progress < 0.65f -> "Descargando APKs si es necesario..."
                    progress < 0.82f -> "Generando informes MobSF..."
                    else -> "Construyendo comparativa..."
                }

                detailMessage = when {
                    progress < 0.20f -> "Enviando al backend las aplicaciones seleccionadas."
                    progress < 0.42f -> "El backend comprueba si ya existen versiones analizadas."
                    progress < 0.65f -> "Si no existe análisis previo, se descarga el APK correspondiente."
                    progress < 0.82f -> "MobSF analiza las aplicaciones y genera informes JSON."
                    else -> "La respuesta final se mostrará al completar el proceso."
                }
            }
        }

        try {
            val result = PiCheckApiClient.requestComparison(
                appA = appA,
                appB = appB,
                downloadApks = true,
            )

            isFinished = true
            hasError = false
            progress = 1f
            statusMessage = "Comparativa completada"
            detailMessage = "La comparativa se ha generado correctamente."

            delay(900)
            onFinished(result)
        } catch (exception: Exception) {
            isFinished = true
            hasError = true
            progress = 1f
            statusMessage = "Error durante la comparación"
            detailMessage = exception.message ?: "Se produjo un error inesperado."
        } finally {
            progressJob.cancel()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "PI-check",
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

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = "Preparando comparación",
                style = MaterialTheme.typography.headlineSmall,
                color = PiCheckBlue,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Descargando, analizando y comparando las aplicaciones seleccionadas.",
                style = MaterialTheme.typography.bodyMedium,
                color = PiCheckDarkText,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(28.dp))

            DownloadAnimationCard(
                appA = appA,
                appB = appB,
                animationStep = animationStep,
                isFinished = isFinished,
                hasError = hasError,
            )

            Spacer(modifier = Modifier.height(28.dp))

            LinearProgressIndicator(
                progress = { animatedProgress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(10.dp),
                color = if (hasError) PiCheckBurgundy else PiCheckBlue,
                trackColor = PiCheckCardBorder,
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "${(animatedProgress * 100).toInt()}%",
                style = MaterialTheme.typography.titleMedium,
                color = PiCheckBlue,
                fontWeight = FontWeight.Bold,
            )

            Spacer(modifier = Modifier.height(18.dp))

            Text(
                text = statusMessage,
                style = MaterialTheme.typography.titleMedium,
                color = if (hasError) PiCheckBurgundy else PiCheckDarkText,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = detailMessage,
                style = MaterialTheme.typography.bodySmall,
                color = PiCheckDarkText,
                textAlign = TextAlign.Center,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis,
            )

            if (hasError) {
                Spacer(modifier = Modifier.height(24.dp))

                Button(
                    onClick = onBack,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBurgundy,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = "Volver al buscador",
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

@Composable
private fun DownloadAnimationCard(
    appA: PlayStoreApp,
    appB: PlayStoreApp,
    animationStep: Int,
    isFinished: Boolean,
    hasError: Boolean,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(
            containerColor = Color.White,
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 3.dp,
        ),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                DownloadAppMiniCard(app = appA)
                DownloadAppMiniCard(app = appB)
            }

            Spacer(modifier = Modifier.height(28.dp))

            ApkToFolderStepAnimation(
                animationStep = animationStep,
                isFinished = isFinished,
                hasError = hasError,
            )
        }
    }
}

@Composable
private fun DownloadAppMiniCard(app: PlayStoreApp) {
    Card(
        modifier = Modifier.size(width = 132.dp, height = 74.dp),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(
            containerColor = PiCheckBackground,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = app.title,
                style = MaterialTheme.typography.bodySmall,
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            Text(
                text = app.appId,
                style = MaterialTheme.typography.bodySmall,
                color = PiCheckBlue,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun ApkToFolderStepAnimation(
    animationStep: Int,
    isFinished: Boolean,
    hasError: Boolean,
) {
    val apkOffset = when {
        isFinished || hasError -> 0.dp
        animationStep == 0 -> (-78).dp
        animationStep == 1 -> 0.dp
        else -> 78.dp
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(116.dp),
        contentAlignment = Alignment.Center,
    ) {
        FolderIcon(
            modifier = Modifier.align(Alignment.CenterEnd),
            isFinished = isFinished,
            hasError = hasError,
        )

        AndroidApkIcon(
            modifier = Modifier
                .align(Alignment.Center)
                .offset(x = apkOffset),
            isFinished = isFinished,
            hasError = hasError,
        )
    }
}

@Composable
private fun AndroidApkIcon(
    modifier: Modifier = Modifier,
    isFinished: Boolean,
    hasError: Boolean,
) {
    val backgroundColor = when {
        hasError -> PiCheckBurgundy
        isFinished -> PiCheckBlue
        else -> PiCheckBurgundy
    }

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            modifier = Modifier.size(width = 44.dp, height = 10.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Bottom,
        ) {
            Box(
                modifier = Modifier
                    .size(width = 4.dp, height = 12.dp)
                    .background(backgroundColor, RoundedCornerShape(4.dp))
            )

            Box(
                modifier = Modifier
                    .size(width = 4.dp, height = 12.dp)
                    .background(backgroundColor, RoundedCornerShape(4.dp))
            )
        }

        Box(
            modifier = Modifier
                .size(width = 66.dp, height = 62.dp)
                .background(backgroundColor, RoundedCornerShape(16.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .background(Color.White, RoundedCornerShape(50))
                    )

                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .background(Color.White, RoundedCornerShape(50))
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "APK",
                    color = Color.White,
                    fontWeight = FontWeight.ExtraBold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun FolderIcon(
    modifier: Modifier = Modifier,
    isFinished: Boolean,
    hasError: Boolean,
) {
    val folderColor = when {
        hasError -> PiCheckBurgundy
        isFinished -> PiCheckBlue
        else -> PiCheckCardBorder
    }

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier = Modifier
                .size(width = 74.dp, height = 18.dp)
                .background(folderColor, RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
        )

        Box(
            modifier = Modifier
                .size(width = 98.dp, height = 64.dp)
                .background(folderColor, RoundedCornerShape(14.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = if (isFinished && !hasError) "✓" else "JSON",
                color = Color.White,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}