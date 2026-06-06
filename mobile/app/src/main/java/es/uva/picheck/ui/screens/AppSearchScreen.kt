package es.uva.picheck.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.IntegrationModel
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.model.RegisteredAppVersion
import es.uva.picheck.data.remote.PiCheckApiClient
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val ElectricBlue = Color(0xFF2D5BFF)

private enum class AppListMode {
    REGISTERED,
    SEARCH
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppSearchScreen() {
    var currentMode by remember { mutableStateOf(AppListMode.REGISTERED) }

    var query by remember { mutableStateOf("") }
    var apps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }
    var analyzedApps by remember { mutableStateOf<List<AnalyzedApp>>(emptyList()) }
    var selectedApps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }

    var comparisonResult by remember { mutableStateOf<PiCheckComparisonAnalysis?>(null) }

    var isLoadingSearch by remember { mutableStateOf(false) }
    var isLoadingAnalyzed by remember { mutableStateOf(false) }
    var showDownloadProgress by remember { mutableStateOf(false) }

    var statusMessage by remember {
        mutableStateOf("Selecciona dos aplicaciones para preparar su comparación.")
    }

    var analyzedStatus by remember {
        mutableStateOf("No hay aplicaciones registradas todavía.")
    }

    val coroutineScope = rememberCoroutineScope()

    fun toggleSelectedApp(app: PlayStoreApp) {
        selectedApps = when {
            selectedApps.any { it.selectionKey() == app.selectionKey() } -> {
                statusMessage = "Aplicación eliminada de la selección."
                selectedApps.filterNot { it.selectionKey() == app.selectionKey() }
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
    }

    suspend fun refreshRegisteredApps(
    showLoadingIndicator: Boolean = true,
    ) {
        if (!showLoadingIndicator && isLoadingAnalyzed) {
            return
        }

        if (showLoadingIndicator) {
            isLoadingAnalyzed = true
            analyzedStatus = "Consultando aplicaciones registradas..."
        }

        try {
            val latestRegisteredApps = PiCheckApiClient.getRegisteredApps()

            analyzedApps = latestRegisteredApps

            analyzedStatus = if (latestRegisteredApps.isEmpty()) {
                "No hay aplicaciones registradas todavía."
            } else {
                "Aplicaciones registradas disponibles: ${latestRegisteredApps.size}"
            }
        } catch (exception: Exception) {
            if (showLoadingIndicator || analyzedApps.isEmpty()) {
                analyzedStatus =
                    "No se pudieron cargar las aplicaciones registradas: ${exception.message}"
            }
        } finally {
            if (showLoadingIndicator) {
                isLoadingAnalyzed = false
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshRegisteredApps(showLoadingIndicator = true)
    }

    LaunchedEffect(currentMode) {
        if (currentMode == AppListMode.REGISTERED) {
            while (true) {
                delay(5_000)
                refreshRegisteredApps(showLoadingIndicator = false)
            }
        }
    }
    
    if (comparisonResult != null) {
        ComparisonResultScreen(
            result = comparisonResult!!,
            onNewComparison = {
                comparisonResult = null
                query = ""
                apps = emptyList()
                selectedApps = emptyList()
                currentMode = AppListMode.REGISTERED
                isLoadingSearch = false
                showDownloadProgress = false
                statusMessage = "Selecciona dos aplicaciones para preparar su comparación."
            },
        )

        return
    }

    if (showDownloadProgress && selectedApps.size == 2) {
        AppDownloadProgressScreen(
            appA = selectedApps[0],
            appB = selectedApps[1],
            onFinished = { result ->
                comparisonResult = result
                showDownloadProgress = false
            },
            onBack = {
                showDownloadProgress = false
                statusMessage = "Selecciona dos aplicaciones para preparar su comparación."
            },
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

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 14.dp, vertical = 12.dp)
        ) {
            SelectedAppsPanel(
                selectedApps = selectedApps,
                onRemove = { appToRemove ->
                    selectedApps = selectedApps.filterNot { it.selectionKey() == appToRemove.selectionKey() }
                    statusMessage = "Aplicación eliminada de la selección."
                },
            )

            Spacer(modifier = Modifier.height(10.dp))

            Button(
                onClick = {
                    if (selectedApps.size == 2) {
                        showDownloadProgress = true
                    }
                },
                enabled = selectedApps.size == 2 && !isLoadingSearch,
                colors = ButtonDefaults.buttonColors(
                    containerColor = PiCheckBlue,
                    contentColor = Color.White,
                ),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Comparar aplicaciones")
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = statusMessage,
                style = MaterialTheme.typography.bodySmall,
                color = PiCheckDarkText,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            Spacer(modifier = Modifier.height(10.dp))

            AppModeSelector(
                currentMode = currentMode,
                onModeSelected = { selectedMode ->
                    currentMode = selectedMode

                    statusMessage = when (selectedMode) {
                        AppListMode.REGISTERED -> "Mostrando aplicaciones registradas en el servidor."
                        AppListMode.SEARCH -> "Busca aplicaciones para añadirlas a la comparación."
                    }
                }
            )

            Spacer(modifier = Modifier.height(12.dp))

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                when (currentMode) {
                    AppListMode.REGISTERED -> {
                        item {
                            SectionTitle(text = "Aplicaciones registradas")
                        }

                        if (isLoadingAnalyzed) {
                            item {
                                LoadingCard(message = "Cargando aplicaciones registradas...")
                            }
                        }

                        if (!isLoadingAnalyzed && analyzedApps.isEmpty()) {
                            item {
                                EmptyAnalyzedAppsCard(message = analyzedStatus)
                            }
                        }

                        if (!isLoadingAnalyzed && analyzedApps.isNotEmpty()) {
                            items(analyzedApps, key = { it.appId }) { analyzedApp ->
                                AnalyzedAppCard(
                                    app = analyzedApp,
                                    selectedKeys = selectedApps.map { it.selectionKey() }.toSet(),
                                    onVersionSelected = { version ->
                                        toggleSelectedApp(analyzedApp.toPlayStoreApp(version))
                                    },
                                )
                            }
                        }
                    }

                    AppListMode.SEARCH -> {
                        item {
                            SectionTitle(text = "Buscar aplicaciones")
                        }

                        item {
                            SearchInputRow(
                                query = query,
                                onQueryChange = { query = it },
                                isLoading = isLoadingSearch,
                                onSearch = {
                                    coroutineScope.launch {
                                        isLoadingSearch = true
                                        statusMessage = "Buscando aplicaciones..."

                                        try {
                                            apps = PiCheckApiClient.searchApps(query)
                                            statusMessage = "Resultados encontrados: ${apps.size}"
                                        } catch (exception: Exception) {
                                            statusMessage = "Error buscando aplicaciones: ${exception.message}"
                                        } finally {
                                            isLoadingSearch = false
                                        }
                                    }
                                }
                            )
                        }

                        if (isLoadingSearch) {
                            item {
                                LoadingCard(message = "Buscando aplicaciones en Google Play...")
                            }
                        }

                        if (!isLoadingSearch && apps.isEmpty()) {
                            item {
                                EmptySearchCard(
                                    message = if (query.length < 2) {
                                        "Introduce al menos dos caracteres para buscar aplicaciones."
                                    } else {
                                        "No hay resultados cargados para la búsqueda actual."
                                    }
                                )
                            }
                        }

                        if (!isLoadingSearch && apps.isNotEmpty()) {
                            items(apps, key = { it.appId }) { app ->
                                val isSelected = selectedApps.any { it.selectionKey() == app.selectionKey() }

                                AppResultCard(
                                    app = app,
                                    isSelected = isSelected,
                                    onClick = {
                                        toggleSelectedApp(app)
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AppModeSelector(
    currentMode: AppListMode,
    onModeSelected: (AppListMode) -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(48.dp),
        shape = RoundedCornerShape(24.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(3.dp),
        ) {
            ModeSelectorSegment(
                text = "Registradas",
                isSelected = currentMode == AppListMode.REGISTERED,
                isLeft = true,
                selectedColor = PiCheckBurgundy,
                modifier = Modifier.weight(1f),
                onClick = {
                    onModeSelected(AppListMode.REGISTERED)
                },
            )

            ModeSelectorSegment(
                text = "Buscar",
                isSelected = currentMode == AppListMode.SEARCH,
                isLeft = false,
                selectedColor = PiCheckBlue,
                modifier = Modifier.weight(1f),
                onClick = {
                    onModeSelected(AppListMode.SEARCH)
                },
            )
        }
    }
}

@Composable
private fun ModeSelectorSegment(
    text: String,
    isSelected: Boolean,
    isLeft: Boolean,
    selectedColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val shape = if (isLeft) {
        RoundedCornerShape(
            topStart = 22.dp,
            bottomStart = 22.dp,
            topEnd = 10.dp,
            bottomEnd = 10.dp,
        )
    } else {
        RoundedCornerShape(
            topStart = 10.dp,
            bottomStart = 10.dp,
            topEnd = 22.dp,
            bottomEnd = 22.dp,
        )
    }

    val backgroundColor = if (isSelected) selectedColor else PiCheckBackground
    val textColor = if (isSelected) Color.White else PiCheckDarkText

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(backgroundColor, shape)
            .clickable { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            color = textColor,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun SearchInputRow(
    query: String,
    onQueryChange: (String) -> Unit,
    isLoading: Boolean,
    onSearch: () -> Unit,
) {
    val searchEnabled = query.length >= 2 && !isLoading

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            label = { Text("Nombre de la aplicación") },
            singleLine = true,
            modifier = Modifier.weight(1f),
        )

        Button(
            onClick = onSearch,
            enabled = searchEnabled,
            colors = ButtonDefaults.buttonColors(
                containerColor = PiCheckBurgundy,
                contentColor = Color.White,
                disabledContainerColor = PiCheckCardBorder,
                disabledContentColor = PiCheckDarkText,
            ),
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.size(56.dp),
            contentPadding = PaddingValues(0.dp),
        ) {
            Icon(
                imageVector = Icons.Filled.Search,
                contentDescription = "Buscar aplicación",
                tint = if (searchEnabled) Color.White else PiCheckDarkText,
                modifier = Modifier.size(28.dp),
            )
        }
    }
}

@Composable
private fun SectionTitle(
    text: String,
) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = PiCheckDarkText,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun LoadingCard(
    message: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                color = PiCheckBurgundy,
                strokeWidth = 2.dp,
            )

            Text(
                text = message,
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun EmptyAnalyzedAppsCard(
    message: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Text(
            text = message,
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            color = PiCheckDarkText,
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun EmptySearchCard(
    message: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(14.dp),
            color = PiCheckDarkText,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun AnalyzedAppCard(
    app: AnalyzedApp,
    selectedKeys: Set<String>,
    onVersionSelected: (RegisteredAppVersion) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val versions = app.versions.ifEmpty {
        listOf(
            RegisteredAppVersion(
                version = app.version,
                integrationModel = app.integrationModel,
                integrationModelShort = app.integrationModel.shortLabel(),
                mobsfStatus = app.mobsfStatus,
                mobsfReportAvailable = app.mobsfReportAvailable,
            )
        )
    }
    val hasSelectedVersion = versions.any { version ->
        selectedKeys.contains(app.toPlayStoreApp(version).selectionKey())
    }
    val borderColor = if (hasSelectedVersion) PiCheckBurgundy else PiCheckCardBorder

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(2.dp, borderColor),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (hasSelectedVersion) 5.dp else 1.dp,
        ),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                AnalyzedAppIcon(app = app)

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = app.name,
                        fontWeight = FontWeight.Bold,
                        color = PiCheckDarkText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    Text(
                        text = "Versiones registradas: ${versions.size}",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                    )

                    Text(
                        text = "Categoría: ${app.category}",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }

                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        imageVector = if (expanded) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                        contentDescription = if (expanded) "Ocultar versiones" else "Mostrar versiones",
                        tint = PiCheckBurgundy,
                        modifier = Modifier
                            .size(32.dp)
                            .clickable { expanded = !expanded },
                    )

                    if (hasSelectedVersion) {
                        Text(
                            text = "✓",
                            color = PiCheckBurgundy,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }

            if (expanded) {
                Spacer(modifier = Modifier.height(10.dp))
                versions.forEach { version ->
                    val versionApp = app.toPlayStoreApp(version)
                    RegisteredVersionRow(
                        version = version,
                        isSelected = selectedKeys.contains(versionApp.selectionKey()),
                        onClick = { onVersionSelected(version) },
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun RegisteredVersionRow(
    version: RegisteredAppVersion,
    isSelected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(if (isSelected) PiCheckBackground else Color(0xFFF8F8FB))
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "Versión ${version.version}",
                color = PiCheckDarkText,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = version.mobsfLabel(),
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        Text(
            text = version.integrationModelShort.ifBlank { version.integrationModel.shortLabel() },
            color = ElectricBlue,
            fontWeight = FontWeight.ExtraBold,
            style = MaterialTheme.typography.titleMedium,
        )

        if (isSelected) {
            Text(
                text = "✓",
                color = PiCheckBurgundy,
                fontWeight = FontWeight.Bold,
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
        Text(
            text = "Aplicaciones seleccionadas",
            style = MaterialTheme.typography.titleSmall,
            color = PiCheckDarkText,
            fontWeight = FontWeight.Bold,
        )

        Spacer(modifier = Modifier.height(8.dp))

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
        modifier = modifier.height(122.dp),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(
            width = 2.dp,
            color = if (hasApp) PiCheckBurgundy else PiCheckCardBorder,
        ),
        colors = CardDefaults.cardColors(
            containerColor = Color.White,
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (hasApp) 4.dp else 1.dp,
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
                        .padding(top = 12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    AppIcon(app = app, size = 42)

                    Spacer(modifier = Modifier.height(6.dp))

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
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (isSelected) 5.dp else 1.dp,
        ),
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            AppIcon(app = app)

            Spacer(modifier = Modifier.size(12.dp))

            Column(
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    text = app.title,
                    style = MaterialTheme.typography.titleSmall,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
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

@Composable
private fun AnalyzedAppIcon(
    app: AnalyzedApp,
    size: Int = 52,
) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .background(PiCheckBlue, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = app.name.firstOrNull()?.uppercase() ?: "?",
            color = Color.White,
            fontWeight = FontWeight.Bold,
        )

        if (!app.icon.isNullOrBlank()) {
            AsyncImage(
                model = app.icon,
                contentDescription = "Icono de ${app.name}",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(size.dp)
                    .clip(CircleShape),
            )
        }
    }
}

private fun AnalyzedApp.toPlayStoreApp(version: RegisteredAppVersion): PlayStoreApp = PlayStoreApp(
    appId = appId,
    title = name,
    developer = developer,
    icon = icon,
    genre = category,
    version = version.version,
    versionDate = version.versionDate,
    selectedVersion = version.version,
    versionCode = version.versionCode,
    integrationModel = version.integrationModel,
    apkSha256 = version.apkSha256,
)

private fun PlayStoreApp.selectionKey(): String = listOf(
    appId,
    selectedVersion ?: version.orEmpty(),
    apkSha256.orEmpty(),
).joinToString("|")

private fun IntegrationModel.shortLabel(): String = when (this) {
    IntegrationModel.HEALTH_CONNECT -> "HC"
    IntegrationModel.LEGACY -> "L"
    IntegrationModel.UNKNOWN -> "?"
}

private fun RegisteredAppVersion.mobsfLabel(): String = when (mobsfStatus) {
    "success" -> if (mobsfReportAvailable) "MobSF OK" else "Pendiente"
    "pending" -> "Pendiente"
    "error" -> "Error"
    "not_analyzed", null -> "No analizada"
    else -> mobsfStatus
}
