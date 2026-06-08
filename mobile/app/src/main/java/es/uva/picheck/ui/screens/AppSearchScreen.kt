package es.uva.picheck.ui.screens

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.BoxWithConstraints
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
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.LocalContext
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
    SEARCH,
    UPLOAD
}

private enum class MainScreenState {
    SELECTION,
    PROGRESS,
    RESULT
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
    var selectedUploadUri by remember { mutableStateOf<Uri?>(null) }
    var selectedUploadName by remember { mutableStateOf<String?>(null) }
    var isUploadingApk by remember { mutableStateOf(false) }
    var uploadStatus by remember { mutableStateOf("Esperando selección de APK/XAPK/APKS/APKM.") }

    var statusMessage by remember {
        mutableStateOf("Selecciona dos aplicaciones para preparar su comparación.")
    }

    var analyzedStatus by remember {
        mutableStateOf("No hay aplicaciones registradas todavía.")
    }

    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current
    val uploadLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            val displayName = context.displayNameForUri(uri)
            selectedUploadUri = uri
            selectedUploadName = displayName
            uploadStatus = "Archivo seleccionado: $displayName"
        }
    }

    fun selectMode(selectedMode: AppListMode) {
        currentMode = selectedMode
        statusMessage = when (selectedMode) {
            AppListMode.REGISTERED -> "Mostrando aplicaciones registradas en el servidor."
            AppListMode.SEARCH -> "Busca aplicaciones para añadirlas a la comparación."
            AppListMode.UPLOAD -> "Importa APKs al servidor; después aparecerán en Registradas."
        }
    }

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
        if (currentMode == AppListMode.REGISTERED || currentMode == AppListMode.UPLOAD) {
            while (true) {
                delay(5_000)
                refreshRegisteredApps(showLoadingIndicator = false)
            }
        }
    }

    val mainScreenState = when {
        comparisonResult != null -> MainScreenState.RESULT
        showDownloadProgress && selectedApps.size == 2 -> MainScreenState.PROGRESS
        else -> MainScreenState.SELECTION
    }

    Crossfade(
        targetState = mainScreenState,
        animationSpec = tween(durationMillis = 240),
        label = "main-screen-transition",
    ) { activeScreen ->
        when (activeScreen) {
            MainScreenState.RESULT -> {
                comparisonResult?.let { result ->
                    ComparisonResultScreen(
                        result = result,
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
                }
            }

            MainScreenState.PROGRESS -> {
                if (selectedApps.size == 2) {
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
                }
            }

            MainScreenState.SELECTION -> {
                Scaffold(
                    topBar = {
                        PiCheckHeader(
                            currentMode = currentMode,
                            onModeSelected = ::selectMode,
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
                        if (currentMode != AppListMode.UPLOAD) {
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
                        }

                        Crossfade(
                            targetState = currentMode,
                            animationSpec = tween(durationMillis = 220),
                            label = "section-transition",
                            modifier = Modifier.weight(1f),
                        ) { activeMode ->
                            LazyColumn(
                                modifier = Modifier.fillMaxSize(),
                                verticalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                when (activeMode) {
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

                                    AppListMode.UPLOAD -> {
                                        item {
                                            SectionTitle(text = "Subir APK")
                                        }

                                        item {
                                            UploadApkCard(
                                                selectedFileName = selectedUploadName,
                                                status = uploadStatus,
                                                isUploading = isUploadingApk,
                                                onPickFile = {
                                                    uploadLauncher.launch(
                                                        arrayOf(
                                                            "application/vnd.android.package-archive",
                                                            "application/zip",
                                                            "application/octet-stream",
                                                            "*/*",
                                                        )
                                                    )
                                                },
                                                onUpload = {
                                                    val uri = selectedUploadUri
                                                    val fileName = selectedUploadName

                                                    if (uri == null || fileName == null) {
                                                        uploadStatus = "Selecciona primero un archivo APK."
                                                        return@UploadApkCard
                                                    }

                                                    coroutineScope.launch {
                                                        isUploadingApk = true
                                                        uploadStatus = "Subiendo APK... Registrando versión..."

                                                        try {
                                                            val result = PiCheckApiClient.uploadApk(
                                                                context = context,
                                                                uri = uri,
                                                                fileName = fileName,
                                                            )
                                                            uploadStatus = if (result.contains("ya estaba registrada")) {
                                                                "La versión ya estaba registrada: $result"
                                                            } else {
                                                                "APK registrado correctamente: $result"
                                                            }
                                                            selectedUploadUri = null
                                                            selectedUploadName = null
                                                            refreshRegisteredApps(showLoadingIndicator = true)
                                                            currentMode = AppListMode.REGISTERED
                                                        } catch (exception: Exception) {
                                                            uploadStatus = "Error al subir APK: ${exception.message}"
                                                        } finally {
                                                            isUploadingApk = false
                                                        }
                                                    }
                                                },
                                            )
                                        }

                                        item {
                                            InstalledAppsExperimentalCard()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PiCheckHeader(
    currentMode: AppListMode,
    onModeSelected: (AppListMode) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PiCheckBurgundy),
    ) {
        CenterAlignedTopAppBar(
            title = {
                Text(
                    text = "PI-check",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                )
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = PiCheckBurgundy,
                titleContentColor = Color.White,
            ),
        )

        HeaderSectionTabs(
            currentMode = currentMode,
            onModeSelected = onModeSelected,
        )
    }
}

@Composable
private fun HeaderSectionTabs(
    currentMode: AppListMode,
    onModeSelected: (AppListMode) -> Unit,
) {
    val tabs = listOf(
        AppListMode.REGISTERED to "Registradas",
        AppListMode.SEARCH to "Buscar",
        AppListMode.UPLOAD to "Subir APK",
    )

    val selectedIndex = tabs.indexOfFirst { it.first == currentMode }
        .coerceAtLeast(0)

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .height(50.dp)
            .padding(horizontal = 10.dp),
    ) {
        val tabWidth = maxWidth / tabs.size.toFloat()

        val indicatorOffset by animateDpAsState(
            targetValue = tabWidth * selectedIndex.toFloat(),
            animationSpec = tween(durationMillis = 260),
            label = "header-tab-indicator-offset",
        )

        Column(
            modifier = Modifier.fillMaxSize(),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                tabs.forEach { (mode, label) ->
                    HeaderSectionTab(
                        text = label,
                        isSelected = currentMode == mode,
                        modifier = Modifier.weight(1f),
                        onClick = { onModeSelected(mode) },
                    )
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp),
            ) {
                Box(
                    modifier = Modifier
                        .offset(x = indicatorOffset)
                        .width(tabWidth)
                        .fillMaxHeight()
                        .padding(horizontal = 18.dp)
                        .clip(
                            RoundedCornerShape(
                                topStart = 3.dp,
                                topEnd = 3.dp,
                            )
                        )
                        .background(Color.White),
                )
            }
        }
    }
}

@Composable
private fun HeaderSectionTab(
    text: String,
    isSelected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val textColor by animateColorAsState(
        targetValue = if (isSelected) {
            Color.White
        } else {
            Color.White.copy(alpha = 0.70f)
        },
        animationSpec = tween(durationMillis = 180),
        label = "header-tab-text-color",
    )

    Box(
        modifier = modifier
            .fillMaxHeight()
            .clip(RoundedCornerShape(10.dp))
            .clickable { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            color = textColor,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.SemiBold,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun UploadApkCard(
    selectedFileName: String?,
    status: String,
    isUploading: Boolean,
    onPickFile: () -> Unit,
    onUpload: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Subir APK",
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
            )

            Text(
                text = selectedFileName ?: "Ningún archivo seleccionado",
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            Text(
                text = status,
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )

            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Button(
                    onClick = onPickFile,
                    enabled = !isUploading,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBurgundy,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text("Seleccionar")
                }

                Button(
                    onClick = onUpload,
                    enabled = selectedFileName != null && !isUploading,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PiCheckBlue,
                        contentColor = Color.White,
                    ),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    if (isUploading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = Color.White,
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Text("Subir")
                    }
                }
            }
        }
    }
}

@Composable
private fun InstalledAppsExperimentalCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        border = BorderStroke(1.dp, PiCheckCardBorder),
        colors = CardDefaults.cardColors(containerColor = Color.White),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Extraer APK instalada",
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Funcionalidad experimental documentada: se prioriza la subida segura desde archivo. Las apps instaladas pueden usar split APKs y restricciones de visibilidad en Android 11+.",
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                text = "Futura mejora: listar apps lanzables, detectar sourceDir/splitSourceDirs y subir solo APK base simple o empaquetar splits de forma explícita.",
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
        }
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
                text = "Fecha: ${version.versionDateLabel()}",
                color = PiCheckDarkText,
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                text = version.analysisLabel(),
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

private fun RegisteredAppVersion.analysisLabel(): String = when (mobsfStatus?.lowercase()) {
    "success" -> if (mobsfReportAvailable) "Analizada: Sí" else "Analizada: No"
    "pending" -> "Análisis: En progreso"
    "error" -> "Error en análisis"
    else -> "Analizada: No"
}

private fun RegisteredAppVersion.versionDateLabel(): String =
    versionDate?.takeIf { it.isNotBlank() } ?: "Fecha desconocida"

private fun Context.displayNameForUri(uri: Uri): String {
    contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (nameIndex >= 0 && cursor.moveToFirst()) {
            return cursor.getString(nameIndex)
        }
    }

    return uri.lastPathSegment?.substringAfterLast('/') ?: "selected.apk"
}
