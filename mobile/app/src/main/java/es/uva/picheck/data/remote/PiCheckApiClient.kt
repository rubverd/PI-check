package es.uva.picheck.data.remote

import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.IntegrationModel
import es.uva.picheck.data.model.PlayStoreApp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

object PiCheckApiClient {
    private const val BASE_URL = "http://10.0.2.2:8000"

    suspend fun searchApps(query: String): List<PlayStoreApp> = withContext(Dispatchers.IO) {
        val encodedQuery = URLEncoder.encode(query, "UTF-8")
        val response = get("/api/apps/search?q=$encodedQuery")
        val json = JSONObject(response)
        val results = json.getJSONArray("results")

        List(results.length()) { index ->
            results.getJSONObject(index).toPlayStoreApp()
        }
    }

    suspend fun requestComparison(
        appA: PlayStoreApp,
        appB: PlayStoreApp,
        downloadApks: Boolean,
    ): String = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("app_a", appA.toComparisonJson())
            .put("app_b", appB.toComparisonJson())
            .put("download_apks", downloadApks)

        post("/api/comparisons/request", body).toString(2)
    }

    suspend fun getAnalyzedApps(): List<AnalyzedApp> = withContext(Dispatchers.IO) {
        val response = get("/api/apps/analyzed")
        val results = JSONObject(response).getJSONArray("results")

        List(results.length()) { index ->
            results.getJSONObject(index).toAnalyzedApp()
        }
    }

    private fun get(path: String): String {
        val connection = (URL("$BASE_URL$path").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 10_000
        }

        return connection.readResponse()
    }

    private fun post(path: String, body: JSONObject): JSONObject {
        val connection = (URL("$BASE_URL$path").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 10_000
            readTimeout = 10_000
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=UTF-8")
            setRequestProperty("Accept", "application/json")
        }

        OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
            writer.write(body.toString())
        }

        return JSONObject(connection.readResponse())
    }

    private fun HttpURLConnection.readResponse(): String {
        val responseCode = responseCode
        val stream = if (responseCode in 200..299) inputStream else errorStream
        val response = stream.bufferedReader().use(BufferedReader::readText)

        disconnect()

        if (responseCode !in 200..299) {
            throw IllegalStateException("HTTP $responseCode: $response")
        }

        return response
    }

    private fun JSONObject.toPlayStoreApp(): PlayStoreApp = PlayStoreApp(
        appId = getString("app_id"),
        title = getString("title"),
        developer = optNullableString("developer"),
        icon = optNullableString("icon"),
        score = optNullableDouble("score"),
        genre = optNullableString("genre"),
        free = optNullableBoolean("free"),
        url = optNullableString("url"),
        version = optNullableString("version"),
        versionDate = optNullableString("version_date"),
    )

    private fun JSONObject.toAnalyzedApp(): AnalyzedApp = AnalyzedApp(
        appId = getString("app_id"),
        name = getString("name"),
        version = getString("version"),
        category = getString("category"),
        analysisDate = getString("analysis_date"),
        integrationModel = when (getString("integration_model")) {
            "health_connect" -> IntegrationModel.HEALTH_CONNECT
            else -> IntegrationModel.LEGACY
        },
    )

    private fun PlayStoreApp.toComparisonJson(): JSONObject = JSONObject()
        .put("app_id", appId)
        .put("title", title)
        .putNullable("developer", developer)
        .putNullable("icon", icon)
        .putNullable("score", score)
        .putNullable("genre", genre)
        .putNullable("url", url)
        .putNullable("version", version)
        .putNullable("version_date", versionDate)

    private fun JSONObject.putNullable(name: String, value: Any?): JSONObject =
        put(name, value ?: JSONObject.NULL)

    private fun JSONObject.optNullableString(name: String): String? =
        if (isNull(name)) null else optString(name)

    private fun JSONObject.optNullableDouble(name: String): Double? =
        if (isNull(name)) null else optDouble(name)

    private fun JSONObject.optNullableBoolean(name: String): Boolean? =
        if (isNull(name)) null else optBoolean(name)
}
