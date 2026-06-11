package es.uva.picheck.data.remote

import android.content.Context
import android.net.Uri
import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.ComparisonDashboard
import es.uva.picheck.data.model.DashboardHeader
import es.uva.picheck.data.model.DashboardSide
import es.uva.picheck.data.model.DashboardTechnicalSummary
import es.uva.picheck.data.model.DashboardVerdictCard
import es.uva.picheck.data.model.DashboardMetric
import es.uva.picheck.data.model.MastgScore
import es.uva.picheck.data.model.PermissionDiff
import es.uva.picheck.data.model.QuickKpi
import es.uva.picheck.data.model.TechnicalFinding
import es.uva.picheck.data.model.PiCheckComparisonAnalysis
import es.uva.picheck.data.model.IntegrationModel
import es.uva.picheck.data.model.PiCheckMobSFReport
import es.uva.picheck.data.model.PlayStoreApp
import es.uva.picheck.data.model.RegisteredAppVersion
import es.uva.picheck.data.model.PiCheckVersionAppInfo
import es.uva.picheck.data.model.PiCheckVersionReport
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.DataOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URLEncoder
import java.net.URL

object PiCheckApiClient {
    private object ApiEnvironment {
        // Cambia solo esta constante para alternar entre entornos.
        // Opciones útiles:
        // - Portátil local / emulador: "https://10.0.2.2:8443"
        // - adb reverse o dispositivo con túnel local: "https://127.0.0.1:8443"
        // - VM UVA pública: "https://virtual.lab.inf.uva.es:20492"
        const val BASE_URL = "https://virtual.lab.inf.uva.es:20492"
    }

    private val BASE_URL = ApiEnvironment.BASE_URL
    private const val MAX_RESPONSE_BODY_BYTES = 10 * 1024 * 1024

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
    ): PiCheckComparisonAnalysis = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("app_a", appA.toComparisonJson())
            .put("app_b", appB.toComparisonJson())
            .put("download_apks", downloadApks)

        val response = post("/api/comparisons/request", body)
        response.toPiCheckComparisonAnalysis()
    }

    suspend fun getRegisteredApps(): List<AnalyzedApp> = withContext(Dispatchers.IO) {
        val response = get("/api/apps/registered")
        val results = JSONObject(response).getJSONArray("results")

        List(results.length()) { index ->
            results.getJSONObject(index).toAnalyzedApp()
        }
    }

    suspend fun getAnalyzedApps(): List<AnalyzedApp> = getRegisteredApps()

    suspend fun uploadApk(
        context: Context,
        uri: Uri,
        fileName: String,
        title: String? = null,
        developer: String? = null,
        category: String? = null,
        sourceLabel: String = "mobile_upload",
        runMobsf: Boolean = false,
    ): String = uploadApkMultipart(
        fileName = fileName,
        title = title,
        developer = developer,
        category = category,
        sourceLabel = sourceLabel,
        runMobsf = runMobsf,
        openInputStream = { context.contentResolver.openInputStream(uri) },
        missingFileMessage = "No se pudo abrir el APK seleccionado",
    )

    suspend fun uploadApkFile(
        file: File,
        fileName: String,
        title: String? = null,
        developer: String? = null,
        category: String? = null,
        sourceLabel: String = "mobile_installed_app",
        runMobsf: Boolean = false,
    ): String = uploadApkMultipart(
        fileName = fileName,
        title = title,
        developer = developer,
        category = category,
        sourceLabel = sourceLabel,
        runMobsf = runMobsf,
        openInputStream = { FileInputStream(file) },
        missingFileMessage = "No se pudo abrir el APK instalado",
    )

    private suspend fun uploadApkMultipart(
        fileName: String,
        title: String?,
        developer: String?,
        category: String?,
        sourceLabel: String,
        runMobsf: Boolean,
        openInputStream: () -> InputStream?,
        missingFileMessage: String,
    ): String = withContext(Dispatchers.IO) {
        val boundary = "----PiCheckBoundary${System.currentTimeMillis()}"
        val connection = (URL("$BASE_URL/api/apps/upload-apk").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 30_000
            readTimeout = 800_000
            doOutput = true
            setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            setRequestProperty("Accept", "application/json")
        }

        DataOutputStream(connection.outputStream).use { output ->
            output.writeFormField(boundary, "title", title ?: fileName.substringBeforeLast('.'))
            output.writeFormField(boundary, "developer", developer.orEmpty())
            output.writeFormField(boundary, "category", category.orEmpty())
            output.writeFormField(boundary, "source_label", sourceLabel)
            output.writeFormField(boundary, "run_mobsf", runMobsf.toString())
            output.writeFileField(boundary, "file", fileName, openInputStream, missingFileMessage)
            output.writeBytes("--$boundary--\r\n")
            output.flush()
        }

        val json = JSONObject(connection.readResponse())
        val app = json.getJSONObject("app")
        val version = json.getJSONObject("version")
        val alreadyRegistered = json.optBoolean("already_registered", false)
        val status = if (alreadyRegistered) "ya estaba registrada" else "registrada"

        "${app.getString("name")} ${version.getString("version")} $status"
    }


    private fun DataOutputStream.writeFormField(boundary: String, name: String, value: String) {
        writeBytes("--$boundary\r\n")
        writeBytes("Content-Disposition: form-data; name=\"$name\"\r\n\r\n")
        writeBytes(value)
        writeBytes("\r\n")
    }

    private fun DataOutputStream.writeFileField(
        boundary: String,
        fieldName: String,
        fileName: String,
        openInputStream: () -> InputStream?,
        missingFileMessage: String,
    ) {
        writeBytes("--$boundary\r\n")
        writeBytes(
            "Content-Disposition: form-data; name=\"$fieldName\"; filename=\"$fileName\"\r\n"
        )
        writeBytes("Content-Type: application/vnd.android.package-archive\r\n\r\n")

        openInputStream()?.use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read == -1) break
                write(buffer, 0, read)
            }
        } ?: throw IllegalStateException(missingFileMessage)

        writeBytes("\r\n")
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
            readTimeout = 800_000
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
        val declaredLength = contentLength
        if (declaredLength > MAX_RESPONSE_BODY_BYTES) {
            disconnect()
            throw IOException(
                "La respuesta del servidor es demasiado grande " +
                    "(${declaredLength / (1024 * 1024)} MB). La comparativa debe generarse como resumen.",
            )
        }

        val stream = if (responseCode in 200..299) inputStream else errorStream
        val response = stream?.use { input ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            var totalRead = 0

            while (true) {
                val read = input.read(buffer)
                if (read == -1) break
                totalRead += read
                if (totalRead > MAX_RESPONSE_BODY_BYTES) {
                    throw IOException(
                        "La respuesta del servidor es demasiado grande. " +
                            "La comparativa debe generarse como resumen.",
                    )
                }
                output.write(buffer, 0, read)
            }

            output.toString(Charsets.UTF_8.name())
        }.orEmpty()

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

    private fun JSONObject.toAnalyzedApp(): AnalyzedApp {
        val versions: List<RegisteredAppVersion> = parseRegisteredAppVersions(
            optJSONArray("versions")
        )
        val latestVersion: RegisteredAppVersion? = versions.firstOrNull()
        val integrationModel = parseIntegrationModel(
            optString("integration_model", latestVersion?.integrationModel?.name ?: "unknown")
        )

        return AnalyzedApp(
            appId = getString("app_id"),
            name = getString("name"),
            developer = optNullableString("developer"),
            icon = optNullableString("icon"),
            version = optString("version", latestVersion?.version ?: "No disponible"),
            category = optString("category", ""),
            analysisDate = optString("analysis_date", optString("version_date", "")),
            integrationModel = integrationModel,
            mobsfStatus = optNullableString("mobsf_status") ?: latestVersion?.mobsfStatus,
            mobsfReportAvailable = optBoolean(
                "mobsf_report_available",
                latestVersion?.mobsfReportAvailable ?: false,
            ),
            versions = versions,
        )
    }

    private fun parseRegisteredAppVersions(array: JSONArray?): List<RegisteredAppVersion> {
        if (array == null) {
            return emptyList()
        }

        return List(array.length()) { index: Int ->
            parseRegisteredAppVersion(array.getJSONObject(index))
        }
    }

    private fun parseRegisteredAppVersion(json: JSONObject): RegisteredAppVersion {
        val integrationModel = parseIntegrationModel(json.optString("integration_model"))
        return RegisteredAppVersion(
            version = json.getString("version"),
            versionCode = json.optNullableInt("version_code"),
            versionDate = json.optNullableString("version_date"),
            integrationModel = integrationModel,
            integrationModelShort = json.optString("integration_model_short", integrationModel.shortLabel()),
            mobsfStatus = json.optNullableString("mobsf_status"),
            mobsfReportAvailable = json.optBoolean("mobsf_report_available", false),
            apkSha256 = json.optNullableString("apk_sha256"),
            rutaApk = json.optNullableString("ruta_apk"),
        )
    }

    private fun JSONObject.toPiCheckComparisonAnalysis(): PiCheckComparisonAnalysis =
        PiCheckComparisonAnalysis(
            comparisonId = getString("comparison_id"),
            status = getString("status"),
            message = getString("message"),
            messages = getJSONArray("messages").toStringList(),
            appA = getJSONObject("app_a").toPiCheckVersionReport(),
            appB = getJSONObject("app_b").toPiCheckVersionReport(),
            idIndiceAplicado = optNullableString("id_indice_aplicado"),
            rawJson = toString(2),
            comparisonJson = optNullableString("comparison_json")
                ?: optNullableJsonAsPrettyString("comparison"),
            dashboard = optJSONObject("dashboard")?.toComparisonDashboard(),
            comparisonArtifactPath = optNullableString("comparison_artifact_path"),
        )


    private fun JSONObject.toComparisonDashboard(): ComparisonDashboard {
        return ComparisonDashboard(
            mastgScore = parseMastgScore(),
            header = optJSONObject("header")?.toDashboardHeader(),
            executiveSummary = optJSONArray("executive_summary")?.toStringList().orEmpty(),
            verdictCards = optJSONArray("verdict_cards")?.toVerdictCards().orEmpty(),
            quickKpis = optJSONArray("quick_kpis")?.toQuickKpis().orEmpty(),
            platformMetrics = optJSONArray("platform_metrics")?.toDashboardMetrics().orEmpty(),
            privacyMetrics = optJSONArray("privacy_metrics")?.toDashboardMetrics().orEmpty(),
            securityMetrics = optJSONArray("security_metrics")?.toDashboardMetrics().orEmpty(),
            exposureMetrics = optJSONArray("exposure_metrics")?.toDashboardMetrics().orEmpty(),
            keyFindings = optJSONArray("key_findings")?.toTechnicalFindings().orEmpty(),
            technicalFindings = optJSONArray("technical_findings")?.toTechnicalFindings().orEmpty(),
            permissionDiff = optJSONObject("permission_diff")?.toPermissionDiff(),
            technicalSummary = optJSONObject("technical_summary")?.toDashboardTechnicalSummary(),
        )
    }

    private fun JSONObject.parseMastgScore(): MastgScore? {
        optJSONObject("mastg")?.let {
            return MastgScore(
                left = it.optNullableFloat("left_score"),
                right = it.optNullableFloat("right_score"),
                status = it.optNullableString("status"),
                label = it.optNullableString("label"),
            )
        }

        return optJSONObject("mastg_score")?.let {
            MastgScore(
                left = it.optNullableFloat("left"),
                right = it.optNullableFloat("right"),
                status = it.optNullableString("status"),
            )
        }
    }

    private fun JSONObject.toDashboardHeader(): DashboardHeader =
        DashboardHeader(
            appName = optNullableString("app_name"),
            left = optJSONObject("left")?.toDashboardSide(),
            right = optJSONObject("right")?.toDashboardSide(),
            leftTitle = optNullableString("left_title"),
            rightTitle = optNullableString("right_title"),
            leftVersion = optNullableString("left_version"),
            rightVersion = optNullableString("right_version"),
            leftIntegrationModel = optNullableString("left_integration_model"),
            rightIntegrationModel = optNullableString("right_integration_model"),
            leftMobsfStatus = optNullableString("left_mobsf_status"),
            rightMobsfStatus = optNullableString("right_mobsf_status"),
            leftIcon = optNullableString("left_icon"),
            rightIcon = optNullableString("right_icon"),
        )

    private fun JSONObject.toDashboardSide(): DashboardSide =
        DashboardSide(
            label = optNullableString("label"),
            appId = optNullableString("app_id"),
            version = optNullableString("version"),
            versionCode = optNullableInt("version_code"),
            integrationModel = optNullableString("integration_model"),
            integrationModelShort = optNullableString("integration_model_short"),
            mobsfStatus = optNullableString("mobsf_status"),
            icon = optNullableString("icon"),
        )

    private fun JSONArray.toVerdictCards(): List<DashboardVerdictCard> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardVerdictCard(
                title = item.optString("title", "Veredicto"),
                winner = item.optNullableString("winner"),
                status = item.optNullableString("status"),
                summary = item.optNullableString("summary"),
            )
        }

    private fun JSONArray.toQuickKpis(): List<QuickKpi> =
        List(length()) { index ->
            val item = getJSONObject(index)
            QuickKpi(
                title = item.optString("title", "KPI"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                winner = item.optNullableString("winner"),
                level = item.optNullableString("level"),
            )
        }

    private fun JSONArray.toDashboardMetrics(): List<DashboardMetric> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardMetric(
                label = item.optString("label", "Métrica"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                preferred = item.optNullableString("preferred"),
                leftExamples = item.optJSONArray("left_examples")?.toStringList().orEmpty(),
                rightExamples = item.optJSONArray("right_examples")?.toStringList().orEmpty(),
                examplesTruncated = item.optBoolean("examples_truncated", false),
            )
        }

    private fun JSONArray.toTechnicalFindings(): List<TechnicalFinding> =
        List(length()) { index ->
            val item = getJSONObject(index)
            TechnicalFinding(
                title = item.optString("title", "Hallazgo técnico"),
                severity = item.optNullableString("severity"),
                affectedSide = item.optNullableString("affected_side"),
                description = item.optNullableString("description"),
                detail = item.optNullableString("detail"),
                summary = item.optNullableString("summary"),
                category = item.optNullableString("category"),
                mastgRelation = item.optNullableString("mastg_relation"),
                relationType = item.optNullableString("relation_type"),
                masvs = item.optNullableString("masvs"),
                cwe = item.optNullableString("cwe"),
            )
        }

    private fun JSONObject.toPermissionDiff(): PermissionDiff =
        PermissionDiff(
            addedInLeft = optJSONArray("added_in_left")?.toStringList().orEmpty(),
            removedInLeft = optJSONArray("removed_in_left")?.toStringList().orEmpty(),
            healthConnectPermissions = optJSONArray("health_connect_permissions")?.toStringList().orEmpty(),
        )

    private fun JSONObject.toDashboardTechnicalSummary(): DashboardTechnicalSummary =
        DashboardTechnicalSummary(
            leftReportAvailable = optNullableBoolean("left_report_available"),
            rightReportAvailable = optNullableBoolean("right_report_available"),
            leftReportSizeBytes = optNullableLong("left_report_size_bytes"),
            rightReportSizeBytes = optNullableLong("right_report_size_bytes"),
            rawReportInResponse = optNullableBoolean("raw_report_in_response"),
        )


    private fun JSONObject.toComparisonDashboard(): ComparisonDashboard =
        ComparisonDashboard(
            mastgScore = parseMastgScore(),
            header = optJSONObject("header")?.toDashboardHeader(),
            executiveSummary = optJSONArray("executive_summary")?.toStringList().orEmpty(),
            verdictCards = optJSONArray("verdict_cards")?.toVerdictCards().orEmpty(),
            quickKpis = optJSONArray("quick_kpis")?.toQuickKpis().orEmpty(),
            platformMetrics = optJSONArray("platform_metrics")?.toDashboardMetrics().orEmpty(),
            privacyMetrics = optJSONArray("privacy_metrics")?.toDashboardMetrics().orEmpty(),
            securityMetrics = optJSONArray("security_metrics")?.toDashboardMetrics().orEmpty(),
            exposureMetrics = optJSONArray("exposure_metrics")?.toDashboardMetrics().orEmpty(),
            keyFindings = optJSONArray("key_findings")?.toTechnicalFindings().orEmpty(),
            technicalFindings = optJSONArray("technical_findings")?.toTechnicalFindings().orEmpty(),
            permissionDiff = optJSONObject("permission_diff")?.toPermissionDiff(),
            technicalSummary = optJSONObject("technical_summary")?.toDashboardTechnicalSummary(),
        )

    private fun JSONObject.parseMastgScore(): MastgScore? {
        optJSONObject("mastg")?.let {
            return MastgScore(
                left = it.optNullableFloat("left_score"),
                right = it.optNullableFloat("right_score"),
                status = it.optNullableString("status"),
                label = it.optNullableString("label"),
            )
        }

        return optJSONObject("mastg_score")?.let {
            MastgScore(
                left = it.optNullableFloat("left"),
                right = it.optNullableFloat("right"),
                status = it.optNullableString("status"),
            )
        }
    }

    private fun JSONObject.toDashboardHeader(): DashboardHeader =
        DashboardHeader(
            appName = optNullableString("app_name"),
            left = optJSONObject("left")?.toDashboardSide(),
            right = optJSONObject("right")?.toDashboardSide(),
            leftTitle = optNullableString("left_title"),
            rightTitle = optNullableString("right_title"),
            leftVersion = optNullableString("left_version"),
            rightVersion = optNullableString("right_version"),
            leftIntegrationModel = optNullableString("left_integration_model"),
            rightIntegrationModel = optNullableString("right_integration_model"),
            leftMobsfStatus = optNullableString("left_mobsf_status"),
            rightMobsfStatus = optNullableString("right_mobsf_status"),
            leftIcon = optNullableString("left_icon"),
            rightIcon = optNullableString("right_icon"),
        )

    private fun JSONObject.toDashboardSide(): DashboardSide =
        DashboardSide(
            label = optNullableString("label"),
            appId = optNullableString("app_id"),
            version = optNullableString("version"),
            versionCode = optNullableInt("version_code"),
            integrationModel = optNullableString("integration_model"),
            integrationModelShort = optNullableString("integration_model_short"),
            mobsfStatus = optNullableString("mobsf_status"),
            icon = optNullableString("icon"),
        )

    private fun JSONArray.toVerdictCards(): List<DashboardVerdictCard> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardVerdictCard(
                title = item.optString("title", "Veredicto"),
                winner = item.optNullableString("winner"),
                status = item.optNullableString("status"),
                summary = item.optNullableString("summary"),
            )
        }

    private fun JSONArray.toQuickKpis(): List<QuickKpi> =
        List(length()) { index ->
            val item = getJSONObject(index)
            QuickKpi(
                title = item.optString("title", "KPI"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                winner = item.optNullableString("winner"),
                level = item.optNullableString("level"),
            )
        }

    private fun JSONArray.toDashboardMetrics(): List<DashboardMetric> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardMetric(
                label = item.optString("label", "Métrica"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                preferred = item.optNullableString("preferred"),
                leftExamples = item.optJSONArray("left_examples")?.toStringList().orEmpty(),
                rightExamples = item.optJSONArray("right_examples")?.toStringList().orEmpty(),
                examplesTruncated = item.optBoolean("examples_truncated", false),
            )
        }

    private fun JSONArray.toTechnicalFindings(): List<TechnicalFinding> =
        List(length()) { index ->
            val item = getJSONObject(index)
            TechnicalFinding(
                title = item.optString("title", "Hallazgo técnico"),
                severity = item.optNullableString("severity"),
                affectedSide = item.optNullableString("affected_side"),
                description = item.optNullableString("description"),
                detail = item.optNullableString("detail"),
                summary = item.optNullableString("summary"),
                category = item.optNullableString("category"),
                mastgRelation = item.optNullableString("mastg_relation"),
                relationType = item.optNullableString("relation_type"),
                masvs = item.optNullableString("masvs"),
                cwe = item.optNullableString("cwe"),
            )
        }

    private fun JSONObject.toPermissionDiff(): PermissionDiff =
        PermissionDiff(
            addedInLeft = optJSONArray("added_in_left")?.toStringList().orEmpty(),
            removedInLeft = optJSONArray("removed_in_left")?.toStringList().orEmpty(),
            healthConnectPermissions = optJSONArray("health_connect_permissions")?.toStringList().orEmpty(),
        )

    private fun JSONObject.toDashboardTechnicalSummary(): DashboardTechnicalSummary =
        DashboardTechnicalSummary(
            leftReportAvailable = optNullableBoolean("left_report_available"),
            rightReportAvailable = optNullableBoolean("right_report_available"),
            leftReportSizeBytes = optNullableLong("left_report_size_bytes"),
            rightReportSizeBytes = optNullableLong("right_report_size_bytes"),
            rawReportInResponse = optNullableBoolean("raw_report_in_response"),
        )


    private fun JSONObject.toComparisonDashboard(): ComparisonDashboard =
        ComparisonDashboard(
            mastgScore = parseMastgScore(),
            header = optJSONObject("header")?.toDashboardHeader(),
            executiveSummary = optJSONArray("executive_summary")?.toStringList().orEmpty(),
            verdictCards = optJSONArray("verdict_cards")?.toVerdictCards().orEmpty(),
            quickKpis = optJSONArray("quick_kpis")?.toQuickKpis().orEmpty(),
            platformMetrics = optJSONArray("platform_metrics")?.toDashboardMetrics().orEmpty(),
            privacyMetrics = optJSONArray("privacy_metrics")?.toDashboardMetrics().orEmpty(),
            securityMetrics = optJSONArray("security_metrics")?.toDashboardMetrics().orEmpty(),
            exposureMetrics = optJSONArray("exposure_metrics")?.toDashboardMetrics().orEmpty(),
            keyFindings = optJSONArray("key_findings")?.toTechnicalFindings().orEmpty(),
            technicalFindings = optJSONArray("technical_findings")?.toTechnicalFindings().orEmpty(),
            permissionDiff = optJSONObject("permission_diff")?.toPermissionDiff(),
            technicalSummary = optJSONObject("technical_summary")?.toDashboardTechnicalSummary(),
        )

    private fun JSONObject.parseMastgScore(): MastgScore? {
        optJSONObject("mastg")?.let {
            return MastgScore(
                left = it.optNullableFloat("left_score"),
                right = it.optNullableFloat("right_score"),
                status = it.optNullableString("status"),
                label = it.optNullableString("label"),
            )
        }

        return optJSONObject("mastg_score")?.let {
            MastgScore(
                left = it.optNullableFloat("left"),
                right = it.optNullableFloat("right"),
                status = it.optNullableString("status"),
            )
        }
    }

    private fun JSONObject.toDashboardHeader(): DashboardHeader =
        DashboardHeader(
            appName = optNullableString("app_name"),
            left = optJSONObject("left")?.toDashboardSide(),
            right = optJSONObject("right")?.toDashboardSide(),
            leftTitle = optNullableString("left_title"),
            rightTitle = optNullableString("right_title"),
            leftVersion = optNullableString("left_version"),
            rightVersion = optNullableString("right_version"),
            leftIntegrationModel = optNullableString("left_integration_model"),
            rightIntegrationModel = optNullableString("right_integration_model"),
            leftMobsfStatus = optNullableString("left_mobsf_status"),
            rightMobsfStatus = optNullableString("right_mobsf_status"),
            leftIcon = optNullableString("left_icon"),
            rightIcon = optNullableString("right_icon"),
        )

    private fun JSONObject.toDashboardSide(): DashboardSide =
        DashboardSide(
            label = optNullableString("label"),
            appId = optNullableString("app_id"),
            version = optNullableString("version"),
            versionCode = optNullableInt("version_code"),
            integrationModel = optNullableString("integration_model"),
            integrationModelShort = optNullableString("integration_model_short"),
            mobsfStatus = optNullableString("mobsf_status"),
            icon = optNullableString("icon"),
        )

    private fun JSONArray.toVerdictCards(): List<DashboardVerdictCard> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardVerdictCard(
                title = item.optString("title", "Veredicto"),
                winner = item.optNullableString("winner"),
                status = item.optNullableString("status"),
                summary = item.optNullableString("summary"),
            )
        }

    private fun JSONArray.toQuickKpis(): List<QuickKpi> =
        List(length()) { index ->
            val item = getJSONObject(index)
            QuickKpi(
                title = item.optString("title", "KPI"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                winner = item.optNullableString("winner"),
                level = item.optNullableString("level"),
            )
        }

    private fun JSONArray.toDashboardMetrics(): List<DashboardMetric> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardMetric(
                label = item.optString("label", "Métrica"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                preferred = item.optNullableString("preferred"),
                leftExamples = item.optJSONArray("left_examples")?.toStringList().orEmpty(),
                rightExamples = item.optJSONArray("right_examples")?.toStringList().orEmpty(),
                examplesTruncated = item.optBoolean("examples_truncated", false),
            )
        }

    private fun JSONArray.toTechnicalFindings(): List<TechnicalFinding> =
        List(length()) { index ->
            val item = getJSONObject(index)
            TechnicalFinding(
                title = item.optString("title", "Hallazgo técnico"),
                severity = item.optNullableString("severity"),
                affectedSide = item.optNullableString("affected_side"),
                description = item.optNullableString("description"),
                detail = item.optNullableString("detail"),
                summary = item.optNullableString("summary"),
                category = item.optNullableString("category"),
                mastgRelation = item.optNullableString("mastg_relation"),
                relationType = item.optNullableString("relation_type"),
                masvs = item.optNullableString("masvs"),
                cwe = item.optNullableString("cwe"),
            )
        }

    private fun JSONObject.toPermissionDiff(): PermissionDiff =
        PermissionDiff(
            addedInLeft = optJSONArray("added_in_left")?.toStringList().orEmpty(),
            removedInLeft = optJSONArray("removed_in_left")?.toStringList().orEmpty(),
            healthConnectPermissions = optJSONArray("health_connect_permissions")?.toStringList().orEmpty(),
        )

    private fun JSONObject.toDashboardTechnicalSummary(): DashboardTechnicalSummary =
        DashboardTechnicalSummary(
            leftReportAvailable = optNullableBoolean("left_report_available"),
            rightReportAvailable = optNullableBoolean("right_report_available"),
            leftReportSizeBytes = optNullableLong("left_report_size_bytes"),
            rightReportSizeBytes = optNullableLong("right_report_size_bytes"),
            rawReportInResponse = optNullableBoolean("raw_report_in_response"),
        )

    private fun JSONArray.toQuickKpis(): List<QuickKpi> =
        List(length()) { index ->
            val item = getJSONObject(index)
            QuickKpi(
                title = item.optString("title", "KPI"),
                leftLabel = item.optNullableString("left_label"),
                rightLabel = item.optNullableString("right_label"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
                winner = item.optNullableString("winner"),
                level = item.optNullableString("level"),
            )
        }

    private fun JSONArray.toDashboardMetrics(): List<DashboardMetric> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardMetric(
                label = item.optString("label", "Métrica"),
                leftValue = item.optNullableFloat("left_value"),
                rightValue = item.optNullableFloat("right_value"),
            )
        }

    private fun JSONArray.toTechnicalFindings(): List<TechnicalFinding> =
        List(length()) { index ->
            val item = getJSONObject(index)
            TechnicalFinding(
                title = item.optString("title", "Hallazgo técnico"),
                severity = item.optNullableString("severity"),
                affectedSide = item.optNullableString("affected_side"),
                description = item.optNullableString("description"),
                detail = item.optNullableString("detail"),
                masvs = item.optNullableString("masvs"),
                cwe = item.optNullableString("cwe"),
            )
        }

    private fun JSONObject.toPiCheckVersionReport(): PiCheckVersionReport =
        PiCheckVersionReport(
            versionApp = getJSONObject("version_app").toPiCheckVersionAppInfo(),
            mobsfReport = getJSONObject("mobsf_report").toPiCheckMobSFReport(),
        )

    private fun JSONObject.toPiCheckVersionAppInfo(): PiCheckVersionAppInfo =
        PiCheckVersionAppInfo(
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
            rutaApk = optNullableString("ruta_apk"),
        )

    private fun JSONObject.toPiCheckMobSFReport(): PiCheckMobSFReport =
        PiCheckMobSFReport(
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
        .putNullable("selected_version", selectedVersion)
        .putNullable("version_code", versionCode)
        .putNullable("integration_model", integrationModel?.name)
        .putNullable("apk_sha256", apkSha256)

    private fun parseIntegrationModel(value: String): IntegrationModel = when (value) {
        "health_connect", "HEALTH_CONNECT" -> IntegrationModel.HEALTH_CONNECT
        "legacy", "LEGACY" -> IntegrationModel.LEGACY
        else -> IntegrationModel.UNKNOWN
    }

    private fun IntegrationModel.shortLabel(): String = when (this) {
        IntegrationModel.HEALTH_CONNECT -> "HC"
        IntegrationModel.LEGACY -> "L"
        IntegrationModel.UNKNOWN -> "?"
    }

    private fun JSONArray.toStringList(): List<String> =
        List(length()) { index -> optString(index) }
            .filter { it.isNotBlank() }

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

    private fun JSONObject.optNullableLong(name: String): Long? =
        if (!has(name) || isNull(name)) null else optLong(name)

    private fun JSONObject.optNullableFloat(name: String): Float? =
        if (!has(name) || isNull(name)) null else optDouble(name).toFloat()

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