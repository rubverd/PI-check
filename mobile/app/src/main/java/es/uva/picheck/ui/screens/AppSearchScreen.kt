package es.uva.picheck.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.IntegrationModel
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.remote.PiCheckApiClient
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import kotlinx.coroutines.launch

private val ElectricBlue = Color(0xFF2D5BFF)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppSearchScreen() {
    var query by remember { mutableStateOf("") }
    var apps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }
    var analyzedApps by remember { mutableStateOf<List<AnalyzedApp>>(emptyList()) }
    var selectedApps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }

    var isLoading by remember { mutableStateOf(false) }
    var isLoadingAnalyzed by remember { mutableStateOf(false) }
    var showDownloadProgress by remember { mutableStateOf(false) }

    var statusMessage by remember {
        mutableStateOf("Selecciona dos aplicaciones para preparar su comparación.")
    }

    var analyzedStatus by remember {
        mutableStateOf("Cargando aplicaciones previamente analizadas...")
    }

    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        isLoadingAnalyzed = true
        analyzedStatus = "Consultando API para aplicaciones analizadas..."

        analyzedApps = try {
            PiCheckApiClient.getAnalyzedApps().also {
                analyzedStatus = if (it.isEmpty()) {
                    "No hay aplicaciones analizadas todavía."
                } else {
                    "Aplicaciones analizadas disponibles: ${it.size}"
                }
            }
        } catch (exception: Exception) {
            analyzedStatus = "No se pudieron cargar las aplicaciones analizadas: ${exception.message}"
            emptyList()
        } finally {
            isLoadingAnalyzed = false
        }
    }

    if (showDownloadProgress && selectedApps.size == 2) {
        AppDownloadProgressScreen(
            appA = selectedApps[0],
            appB = selectedApps[1],
            onFinished = {
                query = ""
                apps = emptyList()
                selectedApps = emptyList()
                isLoading = false
                showDownloadProgress = false
                statusMessage = "Selecciona dos aplicaciones para preparar su comparación."
            }
        )

        return
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

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                SelectedAppsPanel(
                    selectedApps = selectedApps,
                    onRemove = { appToRemove ->
                        selectedApps = selectedApps.filterNot { it.appId == appToRemove.appId }
                        statusMessage = "Aplicación eliminada de la selección."
                    },
                )
            }

            item {
                Text(
                    text = "Aplicaciones previamente analizadas",
                    style = MaterialTheme.typography.titleSmall,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
                )
            }

            if (isLoadingAnalyzed) {
                item {
                    CircularProgressIndicator(color = PiCheckBurgundy)
                }
            }

            if (analyzedApps.isEmpty()) {
                item {
                    EmptyAnalyzedAppsCard(message = analyzedStatus)
                }
            } else {
                items(analyzedApps, key = { it.appId }) { analyzedApp ->
                    AnalyzedAppCard(app = analyzedApp)
                }
            }

            item {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Nombre de la aplicación") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                Button(
                    onClick = {
                        coroutineScope.launch {
                            isLoading = true
                            statusMessage = "Buscando aplicaciones..."

                            try {
                                apps = PiCheckApiClient.searchApps(query)
                                statusMessage = "Resultados encontrados: ${apps.size}"
                            } catch (exception: Exception) {
                                statusMessage = "Error buscando aplicaciones: ${exception.message}"
                            } finally {
                                isLoading = false
                            }
                        }
                    },
                    enabled = query.length >= 2 && !isLoading,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBurgundy,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Buscar")
                }
            }

            if (isLoading) {
                item {
                    CircularProgressIndicator(color = PiCheckBurgundy)
                }
            }

            items(apps, key = { it.appId }) { app ->
                val isSelected = selectedApps.any { it.appId == app.appId }

                AppResultCard(
                    app = app,
                    isSelected = isSelected,
                    onClick = {
                        selectedApps = when {
                            isSelected -> {
                                statusMessage = "Aplicación eliminada de la selección."
                                selectedApps.filterNot { it.appId == app.appId }
                            }

                            selectedApps.size < 2 -> {
                                statusMessage = "Aplicación añadida a la selección."
                                selectedApps + app
                            }

                            else -> {
                                statusMessage = "Ya hay dos aplicaciones seleccionadas. Elimina una para seleccionar otra."
                                selectedApps
                            }
                        }
                    },
                )
            }

            item {
                Button(
                    onClick = {
                        if (selectedApps.size == 2) {
                            showDownloadProgress = true
                        }
                    },
                    enabled = selectedApps.size == 2 && !isLoading,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBlue,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Comparar aplicaciones")
                }
            }

            item {
                Text(
                    text = statusMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 4,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun EmptyAnalyzedAppsCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(12.dp),
            color = PiCheckDarkText,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun AnalyzedAppCard(app: AnalyzedApp) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(2.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = app.name,
                    fontWeight = FontWeight.Bold,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Versión: ${app.version}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Categoría: ${app.category}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Analizada: ${app.analysisDate}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Text(
                text = if (app.integrationModel == IntegrationModel.HEALTH_CONNECT) "HC" else "L",
                color = ElectricBlue,
                fontWeight = FontWeight.ExtraBold,
                style = MaterialTheme.typography.titleMedium,
            )
        }
    }
}

@Composable
private fun SelectedAppsPanel(
    selectedApps: List<PlayStoreApp>,
    onRemove: (PlayStoreApp) -> Unit,
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SelectedAppSlot(
                modifier = Modifier.weight(1f),
                position = 1,
                app = selectedApps.getOrNull(0),
                onRemove = selectedApps.getOrNull(0)?.let { app ->
                    { onRemove(app) }
                },
            )

            SelectedAppSlot(
                modifier = Modifier.weight(1f),
                position = 2,
                app = selectedApps.getOrNull(1),
                onRemove = selectedApps.getOrNull(1)?.let { app ->
                    { onRemove(app) }
                },
            )
        }
    }
}

@Composable
private fun SelectedAppSlot(
    modifier: Modifier = Modifier,
    position: Int,
    app: PlayStoreApp?,
    onRemove: (() -> Unit)?,
) {
    val hasApp = app != null

    Card(
        modifier = modifier.height(130.dp),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(
            width = 2.dp,
            color = if (hasApp) PiCheckBurgundy else PiCheckCardBorder,
        ),
        colors = CardDefaults.cardColors(
            containerColor = Color.White,
        ),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(10.dp),
        ) {
            if (app == null) {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        text = "App $position",
                        color = PiCheckBlue,
                        fontWeight = FontWeight.Bold,
                    )

                    Text(
                        text = "Sin seleccionar",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                    )
                }
            } else {
                Column(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .padding(top = 10.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    AppIcon(app = app, size = 34)

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        text = app.title,
                        color = PiCheckDarkText,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    Text(
                        text = "Versión: ${app.version ?: "No disponible"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    Text(
                        text = " ${app.versionDate ?: "No disponible"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }

                if (onRemove != null) {
                    Box(
                        modifier = Modifier
                            .size(24.dp)
                            .background(PiCheckBurgundy, CircleShape)
                            .clickable { onRemove() }
                            .align(Alignment.TopStart),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "×",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AppResultCard(
    app: PlayStoreApp,
    isSelected: Boolean,
    onClick: () -> Unit,
) {
    val borderColor = if (isSelected) PiCheckBurgundy else PiCheckCardBorder

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(2.dp, borderColor),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AppIcon(app = app)

            Spacer(modifier = Modifier.size(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = app.title,
                    fontWeight = FontWeight.Bold,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Categoría: ${app.genre ?: "No disponible"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Versión: ${app.version ?: "No disponible"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                Text(
                    text = "Fecha versión: ${app.versionDate ?: "No disponible"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            if (isSelected) {
                Text(
                    text = "✓",
                    color = PiCheckBurgundy,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun AppIcon(
    app: PlayStoreApp,
    size: Int = 52,
) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .background(PiCheckBlue, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = app.title.firstOrNull()?.uppercase() ?: "?",
            color = Color.White,
            fontWeight = FontWeight.Bold,
        )

        if (!app.icon.isNullOrBlank()) {
            AsyncImage(
                model = app.icon,
                contentDescription = "Icono de ${app.title}",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(size.dp)
                    .clip(CircleShape),
            )
        }
    }
}