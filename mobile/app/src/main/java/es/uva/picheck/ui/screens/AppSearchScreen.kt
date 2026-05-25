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
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.remote.PiCheckApiClient
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppSearchScreen() {
    var query by remember { mutableStateOf("") }
    var apps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }
    var selectedApps by remember { mutableStateOf<List<PlayStoreApp>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var statusMessage by remember {
        mutableStateOf("Busca aplicaciones en Google Play y selecciona dos para compararlas.")
    }

    val coroutineScope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "PI-check",
                        color = Color.White,
                        fontWeight = FontWeight.Bold
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PiCheckBurgundy
                )
            )
        },
        containerColor = PiCheckBackground
    ) { innerPadding ->

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(14.dp)
        ) {
            SelectedAppsPanel(
                selectedApps = selectedApps,
                onRemove = { appToRemove ->
                    selectedApps = selectedApps.filterNot { it.appId == appToRemove.appId }
                    statusMessage = "Aplicación eliminada de la selección."
                }
            )

            Spacer(modifier = Modifier.height(10.dp))

            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Nombre de la aplicación") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(12.dp))

            Button(
                onClick = {
                    coroutineScope.launch {
                        isLoading = true
                        statusMessage = "Buscando aplicaciones..."

                        try {
                            apps = PiCheckApiClient.searchApps(query)

                            // Importante:
                            // No se limpia selectedApps para que las apps elegidas
                            // sigan persistiendo aunque el usuario haga otra búsqueda.
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
                    contentColor = Color.White
                ),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Buscar")
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Seleccionadas: ${selectedApps.size}/2",
                style = MaterialTheme.typography.bodyMedium,
                color = PiCheckDarkText,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                    color = PiCheckBurgundy
                )

                Spacer(modifier = Modifier.height(8.dp))
            }

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
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
                        }
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Button(
                onClick = {
                    if (selectedApps.size == 2) {
                        coroutineScope.launch {
                            isLoading = true
                            statusMessage = "Enviando solicitud de comparación..."

                            try {
                                val response = PiCheckApiClient.requestComparison(
                                    appA = selectedApps[0],
                                    appB = selectedApps[1],
                                    downloadApks = false
                                )

                                statusMessage = "Solicitud enviada correctamente:\n$response"
                            } catch (exception: Exception) {
                                statusMessage = "Error solicitando comparación: ${exception.message}"
                            } finally {
                                isLoading = false
                            }
                        }
                    }
                },
                enabled = selectedApps.size == 2 && !isLoading,
                colors = ButtonDefaults.buttonColors(
                    containerColor = PiCheckBlue,
                    contentColor = Color.White
                ),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Comparar aplicaciones")
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = statusMessage,
                style = MaterialTheme.typography.bodySmall,
                color = PiCheckDarkText,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@Composable
private fun SelectedAppsPanel(
    selectedApps: List<PlayStoreApp>,
    onRemove: (PlayStoreApp) -> Unit
) {
    Column {
        Text(
            text = "Aplicaciones seleccionadas",
            style = MaterialTheme.typography.titleSmall,
            color = PiCheckDarkText,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            SelectedAppSlot(
                modifier = Modifier.weight(1f),
                position = 1,
                app = selectedApps.getOrNull(0),
                onRemove = selectedApps.getOrNull(0)?.let { app ->
                    { onRemove(app) }
                }
            )

            SelectedAppSlot(
                modifier = Modifier.weight(1f),
                position = 2,
                app = selectedApps.getOrNull(1),
                onRemove = selectedApps.getOrNull(1)?.let { app ->
                    { onRemove(app) }
                }
            )
        }
    }
}

@Composable
private fun SelectedAppSlot(
    modifier: Modifier = Modifier,
    position: Int,
    app: PlayStoreApp?,
    onRemove: (() -> Unit)?
) {
    val hasApp = app != null

    Card(
        modifier = modifier.height(122.dp),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(
            width = 2.dp,
            color = if (hasApp) PiCheckBurgundy else PiCheckCardBorder
        ),
        colors = CardDefaults.cardColors(
            containerColor = Color.White
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (hasApp) 4.dp else 1.dp
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(10.dp)
        ) {
            if (app == null) {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "App $position",
                        style = MaterialTheme.typography.titleSmall,
                        color = PiCheckBlue,
                        fontWeight = FontWeight.Bold
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    Text(
                        text = "Sin seleccionar",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText
                    )
                }
            } else {
                Column(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .padding(top = 12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    AppIcon(
                        app = app,
                        size = 42
                    )

                    Spacer(modifier = Modifier.height(6.dp))

                    Text(
                        text = app.title,
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )

                    Text(
                        text = app.developer ?: "Desarrollador no disponible",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                if (onRemove != null) {
                    Box(
                        modifier = Modifier
                            .size(24.dp)
                            .background(PiCheckBurgundy, CircleShape)
                            .clickable { onRemove() }
                            .align(Alignment.TopStart),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "×",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.bodyMedium
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
    onClick: () -> Unit
) {
    val borderColor = if (isSelected) PiCheckBurgundy else PiCheckCardBorder

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(2.dp, borderColor),
        colors = CardDefaults.cardColors(
            containerColor = Color.White
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (isSelected) 6.dp else 2.dp
        )
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            AppIcon(app = app)

            Spacer(modifier = Modifier.size(12.dp))

            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = app.title,
                    style = MaterialTheme.typography.titleSmall,
                    color = PiCheckDarkText,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                Text(
                    text = app.developer ?: "Desarrollador no disponible",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                Text(
                    text = app.appId,
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckBlue,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                val scoreText = app.score?.let {
                    "Valoración: %.1f".format(it)
                } ?: "Sin valoración"

                val genreText = app.genre ?: "Categoría no disponible"

                Text(
                    text = "$scoreText · $genreText",
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            if (isSelected) {
                Text(
                    text = "✓",
                    color = PiCheckBurgundy,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleLarge
                )
            }
        }
    }
}

@Composable
private fun AppIcon(
    app: PlayStoreApp,
    size: Int = 52
) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .background(PiCheckBlue, CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = app.title.firstOrNull()?.uppercase() ?: "?",
            color = Color.White,
            fontWeight = FontWeight.Bold
        )

        if (!app.icon.isNullOrBlank()) {
            AsyncImage(
                model = app.icon,
                contentDescription = "Icono de ${app.title}",
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .size(size.dp)
                    .clip(CircleShape)
            )
        }
    }
}