package es.uva.picheck.data.remote

import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.ComparisonAnalysisResult
import es.uva.picheck.data.model.IntegrationModel
import es.uva.picheck.data.model.MobSFReportInfo
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.model.VersionAppInfo
import es.uva.picheck.data.model.VersionReportInfo
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

object PiCheckApiClient {
    private const val BASE_URL = "https://192.168.1.48:8443"

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
    ): ComparisonAnalysisResult = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("app_a", appA.toComparisonJson())
            .put("app_b", appB.toComparisonJson())
            .put("download_apks", downloadApks)

        val response = post("/api/comparisons/request", body)
        response.toComparisonAnalysisResult()
    }

    suspend fun getAnalyzedApps(): List<AnalyzedApp> = withContext(Dispatchers.IO) {
        val response = get("/api/apps/registered")
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
            readTimeout = 600_000
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
        developer = optNullableString("developer"),
        icon = optNullableString("icon"),
        version = getString("version"),
        category = optString("category", ""),
        analysisDate = optString("analysis_date", ""),
        integrationModel = when (optString("integration_model")) {
            "health_connect", "HEALTH_CONNECT" -> IntegrationModel.HEALTH_CONNECT
            "legacy", "LEGACY" -> IntegrationModel.LEGACY
            else -> IntegrationModel.UNKNOWN
        },
        mobsfStatus = optNullableString("mobsf_status"),
        mobsfReportAvailable = optBoolean("mobsf_report_available", false),
    )

    private fun JSONObject.toComparisonAnalysisResult(): ComparisonAnalysisResult =
        ComparisonAnalysisResult(
            comparisonId = getString("comparison_id"),
            status = getString("status"),
            message = getString("message"),
            messages = getJSONArray("messages").toStringList(),
            appA = getJSONObject("app_a").toVersionReportInfo(),
            appB = getJSONObject("app_b").toVersionReportInfo(),
            idIndiceAplicado = optNullableString("id_indice_aplicado"),
            rawJson = toString(2),
        )

    private fun JSONObject.toVersionReportInfo(): VersionReportInfo =
        VersionReportInfo(
            versionApp = getJSONObject("version_app").toVersionAppInfo(),
            mobsfReport = getJSONObject("mobsf_report").toMobSFReportInfo(),
        )

    private fun JSONObject.toVersionAppInfo(): VersionAppInfo =
        VersionAppInfo(
            idApp = getString("id_app"),
            version = getString("version"),
            versionCode = optNullableInt("version_code"),
            fechaVersion = optNullableString("fecha_version"),
            categoria = optNullableString("categoria"),
            modeloIntegracion = getString("modelo_integracion"),
            apkSha256 = optNullableString("apk_sha256"),
            estadoMobsf = getString("estado_mobsf"),
            hashMobsf = optNullableString("hash_mobsf"),
            rutaInformeMobsf = optNullableString("ruta_informe_mobsf"),
        )

    private fun JSONObject.toMobSFReportInfo(): MobSFReportInfo =
        MobSFReportInfo(
            available = optBoolean("available", false),
            hashMobsf = optNullableString("hash_mobsf"),
            rutaInforme = optNullableString("ruta_informe"),
            fileName = optNullableString("file_name"),
            scanType = optNullableString("scan_type"),
            jsonReportRaw = optNullableJsonAsPrettyString("json_report"),
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

    private fun JSONArray.toStringList(): List<String> =
        List(length()) { index -> optString(index) }

    private fun JSONObject.putNullable(name: String, value: Any?): JSONObject =
        put(name, value ?: JSONObject.NULL)

    private fun JSONObject.optNullableString(name: String): String? =
        if (!has(name) || isNull(name)) null else optString(name)

    private fun JSONObject.optNullableDouble(name: String): Double? =
        if (!has(name) || isNull(name)) null else optDouble(name)

    private fun JSONObject.optNullableBoolean(name: String): Boolean? =
        if (!has(name) || isNull(name)) null else optBoolean(name)

    private fun JSONObject.optNullableInt(name: String): Int? =
        if (!has(name) || isNull(name)) null else optInt(name)

    private fun JSONObject.optNullableJsonAsPrettyString(name: String): String? {
        if (!has(name) || isNull(name)) {
            return null
        }

        return when (val value = get(name)) {
            is JSONObject -> value.toString(2)
            is JSONArray -> value.toString(2)
            else -> value.toString()
        }
    }
}