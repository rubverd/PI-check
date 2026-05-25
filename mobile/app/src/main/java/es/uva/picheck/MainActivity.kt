package es.uva.picheck

import android.os.Bundle
import androidx.activity.ComponentActivity
import android.util.Log
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import es.uva.picheck.ui.theme.PiCheckBackground
import es.uva.picheck.ui.theme.PiCheckBlue
import es.uva.picheck.ui.theme.PiCheckBurgundy
import es.uva.picheck.ui.theme.PiCheckCardBorder
import es.uva.picheck.ui.theme.PiCheckDarkText
import es.uva.picheck.ui.theme.PiCheckTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

private const val API_BASE_URL = "http://192.168.1.40:8000"
private const val TAG = "PI_CHECK_API"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            PiCheckTheme {
                PiCheckApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PiCheckApp() {
    var serverResponse by remember {
        mutableStateOf("Pulsa el botón para comprobar la comunicación con la API.")
    }

    var isLoading by remember {
        mutableStateOf(false)
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
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {

            Text(
                text = "PI-check",
                style = MaterialTheme.typography.headlineLarge,
                color = PiCheckBlue,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Herramienta híbrida para análisis y comparación de privacidad en aplicaciones Android.",
                style = MaterialTheme.typography.bodyMedium,
                color = PiCheckDarkText,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(32.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = Color.White
                ),
                border = BorderStroke(1.dp, PiCheckCardBorder),
                elevation = CardDefaults.cardElevation(
                    defaultElevation = 4.dp
                )
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {

                    Box(
                        modifier = Modifier
                            .size(64.dp)
                            .background(PiCheckBlue, CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "H",
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.headlineMedium
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = "Historial de comparaciones",
                        style = MaterialTheme.typography.titleMedium,
                        color = PiCheckDarkText,
                        fontWeight = FontWeight.Bold
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "Esta acción enviará una petición preliminar al backend para comprobar la conectividad.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PiCheckDarkText,
                        textAlign = TextAlign.Center
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    Button(
                        onClick = {
                            coroutineScope.launch {
                                isLoading = true

                                serverResponse = try {
                                    sendHistoryMessage()
                                } catch (exception: Exception) {
                                    "Error al conectar con la API:\n${exception.message}"
                                } finally {
                                    isLoading = false
                                }
                            }
                        },
                        enabled = !isLoading,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PiCheckBurgundy,
                            contentColor = Color.White
                        ),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        if (isLoading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text(
                                text = "Consultar historial",
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = Color.White
                )
            ) {
                Text(
                    text = serverResponse,
                    modifier = Modifier.padding(16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = PiCheckDarkText
                )
            }
        }
    }
}

private suspend fun sendHistoryMessage(): String = withContext(Dispatchers.IO) {
    var connection: HttpURLConnection? = null

    try {
        val url = URL("$API_BASE_URL/api/history/ping")

        val jsonBody = """
            {
                "source": "android",
                "message": "Consulta de historial solicitada desde la app móvil PI-check"
            }
        """.trimIndent()

        Log.d(TAG, "Enviando petición a: $url")
        Log.d(TAG, "Cuerpo enviado: $jsonBody")

        connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 5000
        connection.readTimeout = 5000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        connection.setRequestProperty("Accept", "application/json")

        connection.outputStream.use { outputStream ->
            outputStream.write(jsonBody.toByteArray(Charsets.UTF_8))
        }

        val statusCode = connection.responseCode

        val responseStream = if (statusCode in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream
        }

        val responseText = responseStream
            ?.bufferedReader()
            ?.use { it.readText() }
            .orEmpty()

        Log.d(TAG, "Código HTTP recibido: $statusCode")
        Log.d(TAG, "Respuesta recibida: $responseText")

        "Código HTTP: $statusCode\n\nRespuesta de la API:\n$responseText"

    } catch (exception: Exception) {
        Log.e(TAG, "Error en la comunicación con la API", exception)
        throw exception
    } finally {
        connection?.disconnect()
    }

}