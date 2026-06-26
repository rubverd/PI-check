package es.uva.picheck.data.remote

import android.content.Context
import android.net.Uri
import android.util.Log
import es.uva.picheck.data.model.AnalyzedApp
import es.uva.picheck.data.model.ComparisonDashboard
import es.uva.picheck.data.model.DashboardHeader
import es.uva.picheck.data.model.DashboardSide
import es.uva.picheck.data.model.DashboardTechnicalSummary
import es.uva.picheck.data.model.DashboardVerdictCard
import es.uva.picheck.data.model.DashboardMetric
import es.uva.picheck.data.model.MastgIndexOption
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
    private const val DASHBOARD_LOG_TAG = "PiCheckDashboard"
    const val DEFAULT_MASTG_INDEX_ID = "picheck_mhealth_v1"
    private const val DASHBOARD_DEBUG = true

    suspend fun searchApps(query: String): List<PlayStoreApp> = withContext(Dispatchers.IO) {
        val encodedQuery = URLEncoder.encode(query, "UTF-8")
        val response = get("/api/apps/search?q=$encodedQuery")
        val json = JSONObject(response)
        val results = json.getJSONArray("results")

        List(results.length()) { index ->
            results.getJSONObject(index).toPlayStoreApp()
        }
    }


    suspend fun getMastgIndexes(): List<MastgIndexOption> = withContext(Dispatchers.IO) {
        val response = get("/api/mastg/indexes")
        val array = JSONArray(response)
        List(array.length()) { index ->
            val item = array.getJSONObject(index)
            MastgIndexOption(
                id = item.optString("id_indice"),
                name = item.optString("nombre", item.optString("id_indice")),
                description = item.optNullableString("descripcion"),
                testCount = item.optIntOrNull("total_pruebas"),
            )
        }
    }

    suspend fun requestComparison(
        appA: PlayStoreApp,
        appB: PlayStoreApp,
        downloadApks: Boolean,
        mastgIndexId: String = DEFAULT_MASTG_INDEX_ID,
    ): PiCheckComparisonAnalysis = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("app_a", appA.toComparisonJson())
            .put("app_b", appB.toComparisonJson())
            .put("download_apks", downloadApks)
            .put("mastg_index_id", mastgIndexId)

        val response = post("/api/comparisons/request", body)
        response.logComparisonResponseDiagnostics()
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


    private fun JSONObject.logComparisonResponseDiagnostics() {
        debugLog("Comparison response received. length=${toString().length}")
        debugLog("Root keys=${keysListLimited()}")
        val comparisonObject = optJSONObject("comparison")
        val rootHighlights = optJSONObject("raw_mobsf_highlights")
        val nestedHighlights = comparisonObject?.optJSONObject("raw_mobsf_highlights")
        debugLog("hasRootComparison=${comparisonObject != null}")
        debugLog("hasRootHighlights=${rootHighlights != null}")
        debugLog("hasNestedHighlights=${nestedHighlights != null}")
        val dashboardFromBackend = optJSONObject("dashboard") != null || comparisonObject?.optJSONObject("dashboard") != null
        debugLog("dashboardFromBackend=$dashboardFromBackend")
    }

    private fun debugLog(message: String) {
        if (DASHBOARD_DEBUG) Log.d(DASHBOARD_LOG_TAG, message)
    }

    private fun ComparisonDashboard?.logDashboardMetrics() {
        val dashboard = this ?: return
        debugLog("platformMetrics=${dashboard.platformMetrics.size}")
        debugLog("privacyMetrics=${dashboard.privacyMetrics.size}")
        debugLog("securityMetrics=${dashboard.securityMetrics.size}")
        debugLog("exposureMetrics=${dashboard.exposureMetrics.size}")
        dashboard.platformMetrics.take(3).forEach {
            debugLog("platform metric ${it.label}: ${it.leftLabel}/${it.rightLabel} values=${it.leftValue}/${it.rightValue}")
        }
    }

    private fun JSONObject.keysListLimited(limit: Int = 30): List<String> {
        val result = mutableListOf<String>()
        val iterator = keys()
        while (iterator.hasNext() && result.size < limit) {
            result.add(iterator.next())
        }
        return result
    }

    private fun JSONObject.comparisonPayload(): JSONObject = optJSONObject("comparison") ?: this

    private fun JSONObject.rawHighlightsPayload(): JSONObject? {
        val comparisonPayload = comparisonPayload()
        return optJSONObject("raw_mobsf_highlights")
            ?: comparisonPayload.optJSONObject("raw_mobsf_highlights")
    }

    private fun JSONObject.dashboardPayload(): JSONObject? {
        val comparisonPayload = comparisonPayload()
        return optJSONObject("dashboard")
            ?: comparisonPayload.optJSONObject("dashboard")
    }

    private fun JSONObject.leftComparisonSide(): JSONObject? = comparisonPayload().optJSONObject("left")

    private fun JSONObject.rightComparisonSide(): JSONObject? = comparisonPayload().optJSONObject("right")

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

    private fun JSONObject.toPiCheckComparisonAnalysis(): PiCheckComparisonAnalysis {
        val comparisonJson = optNullableString("comparison_json")
            ?: optNullableJsonAsPrettyString("comparison")
        val apiDashboard = dashboardPayload()?.toComparisonDashboard()
        val derivedDashboardFromComparison = comparisonJson
            ?.let { runCatching { JSONObject(it).toDerivedComparisonDashboard() }.getOrNull() }
        val derivedDashboardFromResponse = toDerivedComparisonDashboard()
        val finalDashboard = when {
            apiDashboard.hasUsableDashboardData() -> apiDashboard
            derivedDashboardFromComparison.hasUsableDashboardData() -> derivedDashboardFromComparison
            derivedDashboardFromResponse.hasUsableDashboardData() -> derivedDashboardFromResponse
            else -> apiDashboard ?: derivedDashboardFromComparison ?: derivedDashboardFromResponse
        }
        finalDashboard.logDashboardMetrics()

        return PiCheckComparisonAnalysis(
            comparisonId = getString("comparison_id"),
            status = getString("status"),
            message = getString("message"),
            messages = optJSONArray("messages")?.toStringList().orEmpty(),
            appA = getJSONObject("app_a").toPiCheckVersionReport(),
            appB = getJSONObject("app_b").toPiCheckVersionReport(),
            idIndiceAplicado = optNullableString("id_indice_aplicado"),
            rawJson = toString(2),
            comparisonJson = comparisonJson,
            dashboard = finalDashboard,
            comparisonArtifactPath = optNullableString("comparison_artifact_path"),
        )
    }


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
            name = optNullableString("name"),
            appName = optNullableString("app_name"),
            title = optNullableString("title"),
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
                leftLabel = item.optNullableStringAny("left_label", "leftLabel", "left_text", "health_connect_label", "hc_label"),
                rightLabel = item.optNullableStringAny("right_label", "rightLabel", "right_text", "legacy_label", "l_label"),
                leftValue = item.optNullableFloatAny("left_value", "left", "leftValue", "health_connect_value", "hc_value"),
                rightValue = item.optNullableFloatAny("right_value", "right", "rightValue", "legacy_value", "l_value"),
                winner = item.optNullableString("winner"),
                level = item.optNullableString("level"),
            )
        }

    private fun JSONArray.toDashboardMetrics(): List<DashboardMetric> =
        List(length()) { index ->
            val item = getJSONObject(index)
            DashboardMetric(
                label = item.optString("label", "Métrica"),
                leftValue = item.optNullableFloatAny("left_value", "left", "leftValue", "health_connect_value", "hc_value"),
                rightValue = item.optNullableFloatAny("right_value", "right", "rightValue", "legacy_value", "l_value"),
                leftLabel = item.optNullableStringAny("left_label", "leftLabel", "left_text", "health_connect_label", "hc_label"),
                rightLabel = item.optNullableStringAny("right_label", "rightLabel", "right_text", "legacy_label", "l_label"),
                preferred = item.optNullableStringAny("preferred", "direction"),
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

    private fun ComparisonDashboard?.hasUsableDashboardData(): Boolean {
        if (this == null) return false
        val allMetrics = platformMetrics + privacyMetrics + securityMetrics + exposureMetrics
        return allMetrics.any { it.leftValue != null || it.rightValue != null || !it.leftLabel.isNullOrBlank() || !it.rightLabel.isNullOrBlank() } ||
                quickKpis.any { it.leftValue != null || it.rightValue != null || !it.leftLabel.isNullOrBlank() || !it.rightLabel.isNullOrBlank() }
    }

    private fun JSONObject.toDerivedComparisonDashboard(): ComparisonDashboard? {
        val comparison = comparisonPayload()
        val rawHighlights = rawHighlightsPayload() ?: return null
        debugLog("Using locally derived dashboard from raw_mobsf_highlights")
        val leftReport = rawHighlights.optJSONObject("left") ?: return null
        val rightReport = rawHighlights.optJSONObject("right") ?: return null
        val leftMeta = leftComparisonSide()
        val rightMeta = rightComparisonSide()
        debugLog("LEFT raw keys=${leftReport.keysListLimited()}")
        debugLog("RIGHT raw keys=${rightReport.keysListLimited()}")
        val leftTargetRaw = leftReport.optString("target_sdk")
        val leftMinRaw = leftReport.optString("min_sdk")
        val rightTargetRaw = rightReport.optString("target_sdk")
        val rightMinRaw = rightReport.optString("min_sdk")
        debugLog("LEFT target=$leftTargetRaw min=$leftMinRaw")
        debugLog("RIGHT target=$rightTargetRaw min=$rightMinRaw")

        val leftModel = leftMeta?.optNullableString("integration_model")
            ?: comparison.optJSONObject("summary")?.optNullableString("left_model")
            ?: "HEALTH_CONNECT"
        val rightModel = rightMeta?.optNullableString("integration_model")
            ?: comparison.optJSONObject("summary")?.optNullableString("right_model")
            ?: "LEGACY"

        val leftPermissions = leftReport.permissionNames()
        val rightPermissions = rightReport.permissionNames()
        val leftTarget = leftReport.optNullableIntFromString("target_sdk")
        val rightTarget = rightReport.optNullableIntFromString("target_sdk")
        val leftMin = leftReport.optNullableIntFromString("min_sdk")
        val rightMin = rightReport.optNullableIntFromString("min_sdk")
        val leftDangerous = leftReport.countDangerousPermissions()
        val rightDangerous = rightReport.countDangerousPermissions()
        val leftHcPermissions = leftPermissions.count { it.isHealthConnectPermission() }
        val rightHcPermissions = rightPermissions.count { it.isHealthConnectPermission() }
        debugLog("LEFT permissions=${leftPermissions.size} RIGHT permissions=${rightPermissions.size}")
        debugLog("LEFT dangerous=$leftDangerous RIGHT dangerous=$rightDangerous")
        debugLog("LEFT hcPerms=$leftHcPermissions RIGHT hcPerms=$rightHcPermissions")
        val leftHigh = leftReport.totalFindingsBySeverity("high")
        val rightHigh = rightReport.totalFindingsBySeverity("high")
        val leftWarning = leftReport.totalFindingsBySeverity("warning")
        val rightWarning = rightReport.totalFindingsBySeverity("warning")
        val leftExposureScore = leftReport.trackerCount() + leftReport.collectionSize("domains") + leftReport.httpUrlCount()
        val rightExposureScore = rightReport.trackerCount() + rightReport.collectionSize("domains") + rightReport.httpUrlCount()

        val platformMetrics = listOf(
            dashboardMetric("API objetivo (targetSdk)", leftTarget, rightTarget, "higher"),
            dashboardMetric("API mínima (minSdk)", leftMin, rightMin, "higher"),
        )

        val privacyMetrics = listOf(
            dashboardMetric("Permisos peligrosos", leftDangerous, rightDangerous, "lower"),
            dashboardMetric("Permisos Health Connect", leftHcPermissions, rightHcPermissions, "context"),
            dashboardMetric("Permisos de ubicación", leftPermissions.countLocationPermissions(), rightPermissions.countLocationPermissions(), "lower"),
            dashboardMetric("Permisos almacenamiento/media", leftPermissions.countStoragePermissions(), rightPermissions.countStoragePermissions(), "lower"),
            dashboardMetric("Permisos sensores/actividad", leftPermissions.countSensorOrActivityPermissions(), rightPermissions.countSensorOrActivityPermissions(), "context"),
        )

        val securityMetrics = listOf(
            dashboardMetric("Hallazgos HIGH", leftHigh, rightHigh, "lower"),
            dashboardMetric("Hallazgos WARNING", leftWarning, rightWarning, "lower"),
            dashboardMetric("Tráfico en claro", leftReport.hasCleartextTraffic().toIntFlag(), rightReport.hasCleartextTraffic().toIntFlag(), "lower", "activo", "activo"),
            dashboardMetric("allowBackup activo", leftReport.hasAllowBackup().toIntFlag(), rightReport.hasAllowBackup().toIntFlag(), "lower", "activo", "activo"),
            dashboardMetric("Componentes exportados", leftReport.countExportedComponents(), rightReport.countExportedComponents(), "lower"),
            dashboardMetric("Logging", leftReport.hasCodeFinding("android_logging").toIntFlag(), rightReport.hasCodeFinding("android_logging").toIntFlag(), "lower", "detectado", "detectado"),
            dashboardMetric("Almacenamiento externo", leftReport.hasCodeFinding("android_read_write_external").toIntFlag(), rightReport.hasCodeFinding("android_read_write_external").toIntFlag(), "lower", "detectado", "detectado"),
            dashboardMetric("WebView inseguro", leftReport.countCodeFindingsMatching("webview"), rightReport.countCodeFindingsMatching("webview"), "lower"),
            dashboardMetric("Criptografía débil", leftReport.countWeakCryptoFindings(), rightReport.countWeakCryptoFindings(), "lower"),
            dashboardMetric("Binarios sin Stack Canary", leftReport.countStackCanaryHighFindings(), rightReport.countStackCanaryHighFindings(), "lower"),
        )

        val exposureMetrics = listOf(
            dashboardMetric("Trackers", leftReport.trackerCount(), rightReport.trackerCount(), "lower"),
            dashboardMetric("Dominios de red", leftReport.collectionSize("domains"), rightReport.collectionSize("domains"), "lower"),
            dashboardMetric("URLs extraídas", leftReport.collectionSize("urls"), rightReport.collectionSize("urls"), "lower"),
            dashboardMetric("URLs HTTP", leftReport.httpUrlCount(), rightReport.httpUrlCount(), "lower"),
            dashboardMetric("Emails detectados", leftReport.collectionSize("emails"), rightReport.collectionSize("emails"), "lower"),
            dashboardMetric("Firebase URLs", leftReport.collectionSize("firebase_urls"), rightReport.collectionSize("firebase_urls"), "lower"),
        )

        val keyFindings = (leftReport.importantFindings("left") + rightReport.importantFindings("right"))
            .sortedWith(compareBy<TechnicalFinding> { severityRank(it.severity) }.thenBy { it.title })
            .take(16)

        return ComparisonDashboard(
            mastgScore = MastgScore(
                left = null,
                right = null,
                status = "pending",
                label = "Índice MASTG pendiente",
            ),
            header = DashboardHeader(
                appName = leftMeta?.optNullableString("name")
                    ?: rightMeta?.optNullableString("name")
                    ?: leftReport.optNullableString("app_name")
                    ?: "Comparativa",
                left = DashboardSide(
                    label = leftMeta?.optNullableString("name") ?: leftMeta?.optNullableString("title") ?: leftReport.optNullableString("app_name"),
                    name = leftMeta?.optNullableString("name"),
                    appName = leftReport.optNullableString("app_name"),
                    title = leftMeta?.optNullableString("title"),
                    appId = leftMeta?.optNullableString("app_id") ?: leftReport.optNullableString("package_name"),
                    version = leftMeta?.optNullableString("version") ?: leftReport.optNullableString("version_name"),
                    versionCode = leftMeta?.optNullableInt("version_code"),
                    integrationModel = leftModel,
                    integrationModelShort = modelShortLabel(leftModel),
                    mobsfStatus = leftMeta?.optNullableString("mobsf_status") ?: "SUCCESS",
                    icon = leftMeta?.optNullableString("icon"),
                ),
                right = DashboardSide(
                    label = rightMeta?.optNullableString("name") ?: rightMeta?.optNullableString("title") ?: rightReport.optNullableString("app_name"),
                    name = rightMeta?.optNullableString("name"),
                    appName = rightReport.optNullableString("app_name"),
                    title = rightMeta?.optNullableString("title"),
                    appId = rightMeta?.optNullableString("app_id") ?: rightReport.optNullableString("package_name"),
                    version = rightMeta?.optNullableString("version") ?: rightReport.optNullableString("version_name"),
                    versionCode = rightMeta?.optNullableInt("version_code"),
                    integrationModel = rightModel,
                    integrationModelShort = modelShortLabel(rightModel),
                    mobsfStatus = rightMeta?.optNullableString("mobsf_status") ?: "SUCCESS",
                    icon = rightMeta?.optNullableString("icon"),
                ),
            ),
            executiveSummary = buildExecutiveSummary(
                leftTarget = leftTarget,
                rightTarget = rightTarget,
                leftDangerous = leftDangerous,
                rightDangerous = rightDangerous,
                leftHcPermissions = leftHcPermissions,
                rightHcPermissions = rightHcPermissions,
                leftHigh = leftHigh,
                rightHigh = rightHigh,
                leftExposureScore = leftExposureScore,
                rightExposureScore = rightExposureScore,
            ),
            verdictCards = buildVerdictCards(
                leftTarget = leftTarget,
                rightTarget = rightTarget,
                leftDangerous = leftDangerous,
                rightDangerous = rightDangerous,
                leftHigh = leftHigh,
                rightHigh = rightHigh,
                leftExposureScore = leftExposureScore,
                rightExposureScore = rightExposureScore,
            ),
            quickKpis = listOf(
                quickKpi("Plataforma Android", leftTarget, rightTarget, "targetSdk ${leftTarget ?: "N/D"}", "targetSdk ${rightTarget ?: "N/D"}", "higher"),
                quickKpi("Permisos sensibles", leftDangerous, rightDangerous, "$leftDangerous peligrosos", "$rightDangerous peligrosos", "lower", forceReview = leftHcPermissions > rightHcPermissions),
                quickKpi("Riesgos MobSF", leftHigh, rightHigh, "$leftHigh HIGH", "$rightHigh HIGH", "lower"),
                quickKpi("Exposición externa", leftExposureScore, rightExposureScore, "$leftExposureScore señales", "$rightExposureScore señales", "lower"),
            ),
            platformMetrics = platformMetrics,
            privacyMetrics = privacyMetrics,
            securityMetrics = securityMetrics,
            exposureMetrics = exposureMetrics,
            keyFindings = keyFindings,
            technicalFindings = keyFindings,
            permissionDiff = PermissionDiff(
                addedInLeft = (leftPermissions - rightPermissions).sorted(),
                removedInLeft = (rightPermissions - leftPermissions).sorted(),
                healthConnectPermissions = (leftPermissions + rightPermissions).filter { it.isHealthConnectPermission() }.distinct().sorted(),
            ),
            technicalSummary = DashboardTechnicalSummary(
                leftReportAvailable = true,
                rightReportAvailable = true,
                rawReportInResponse = true,
            ),
        )
    }

    private fun dashboardMetric(
        label: String,
        left: Int?,
        right: Int?,
        preferred: String,
        activeLabel: String? = null,
        activeRightLabel: String? = null,
    ): DashboardMetric = DashboardMetric(
        label = label,
        leftValue = left?.toFloat(),
        rightValue = right?.toFloat(),
        leftLabel = booleanMetricLabel(left, activeLabel),
        rightLabel = booleanMetricLabel(right, activeRightLabel),
        preferred = preferred,
    )

    private fun booleanMetricLabel(value: Int?, activeLabel: String?): String? {
        if (value == null) return null
        if (activeLabel == null) return value.toString()
        return if (value > 0) activeLabel else "no"
    }

    private fun quickKpi(
        title: String,
        left: Int?,
        right: Int?,
        leftLabel: String,
        rightLabel: String,
        preferred: String,
        forceReview: Boolean = false,
    ): QuickKpi {
        val winner = if (forceReview) "review" else winnerByPreference(left, right, preferred)
        return QuickKpi(
            title = title,
            leftLabel = leftLabel,
            rightLabel = rightLabel,
            leftValue = left?.toFloat(),
            rightValue = right?.toFloat(),
            winner = winner,
            level = when (winner) {
                "left" -> "positive"
                "right" -> "risk"
                "tie" -> "neutral"
                else -> "warning"
            },
        )
    }

    private fun buildExecutiveSummary(
        leftTarget: Int?,
        rightTarget: Int?,
        leftDangerous: Int,
        rightDangerous: Int,
        leftHcPermissions: Int,
        rightHcPermissions: Int,
        leftHigh: Int,
        rightHigh: Int,
        leftExposureScore: Int,
        rightExposureScore: Int,
    ): List<String> {
        val summary = mutableListOf<String>()
        if ((leftTarget ?: 0) > (rightTarget ?: 0)) {
            summary += "La versión Health Connect utiliza una API objetivo más reciente, lo que indica mayor adaptación a restricciones modernas de Android."
        }
        if (leftHcPermissions > rightHcPermissions) {
            summary += "La versión Health Connect introduce permisos específicos de salud, más granulares que los permisos legacy genéricos."
        }
        summary += when {
            leftExposureScore < rightExposureScore -> "La versión Health Connect reduce señales de exposición externa agregadas, como trackers, dominios o URLs HTTP."
            leftExposureScore > rightExposureScore -> "La versión Health Connect mantiene más señales de exposición externa y requiere revisión adicional."
            else -> "La exposición externa agregada es similar en ambas versiones."
        }
        summary += when {
            leftHigh < rightHigh -> "La versión Health Connect reduce los hallazgos HIGH de MobSF, aunque no implica ausencia total de riesgo."
            leftHigh > rightHigh -> "La versión Health Connect presenta más hallazgos HIGH de MobSF en esta comparativa concreta."
            else -> "Los hallazgos HIGH de MobSF son similares en ambas versiones."
        }
        if (leftDangerous > rightDangerous) {
            summary += "El número de permisos peligrosos no baja necesariamente con Health Connect; conviene revisar su justificación funcional."
        }
        return summary.take(5)
    }

    private fun buildVerdictCards(
        leftTarget: Int?,
        rightTarget: Int?,
        leftDangerous: Int,
        rightDangerous: Int,
        leftHigh: Int,
        rightHigh: Int,
        leftExposureScore: Int,
        rightExposureScore: Int,
    ): List<DashboardVerdictCard> = listOf(
        DashboardVerdictCard(
            title = "Plataforma Android",
            winner = winnerByPreference(leftTarget, rightTarget, "higher"),
            status = if ((leftTarget ?: 0) >= (rightTarget ?: 0)) "positive" else "warning",
            summary = "Compara targetSdk/minSdk para valorar la madurez frente a versiones modernas de Android.",
        ),
        DashboardVerdictCard(
            title = "Permisos sensibles",
            winner = "review",
            status = if (leftDangerous <= rightDangerous) "positive" else "warning",
            summary = "Los permisos Health Connect se analizan aparte: pueden aumentar el número total, pero aportan granularidad sobre datos de salud.",
        ),
        DashboardVerdictCard(
            title = "Riesgos MobSF",
            winner = winnerByPreference(leftHigh, rightHigh, "lower"),
            status = if (leftHigh <= rightHigh) "positive" else "risk",
            summary = "Resume hallazgos HIGH/WARNING en manifest, código, certificado y binarios nativos.",
        ),
        DashboardVerdictCard(
            title = "Exposición externa",
            winner = winnerByPreference(leftExposureScore, rightExposureScore, "lower"),
            status = if (leftExposureScore <= rightExposureScore) "positive" else "warning",
            summary = "Agrupa trackers, dominios, URLs y URLs HTTP detectadas en el análisis estático.",
        ),
    )

    private fun winnerByPreference(left: Int?, right: Int?, preferred: String): String {
        if (left == null || right == null) return "review"
        if (left == right) return "tie"
        return when (preferred) {
            "higher" -> if (left > right) "left" else "right"
            "lower" -> if (left < right) "left" else "right"
            else -> "review"
        }
    }

    private fun modelDisplayName(model: String?): String =
        if (model?.contains("health", ignoreCase = true) == true) "Health Connect" else if (model?.contains("legacy", ignoreCase = true) == true) "Legacy" else "Modelo desconocido"

    private fun modelShortLabel(model: String?): String =
        if (model?.contains("health", ignoreCase = true) == true) "HC" else if (model?.contains("legacy", ignoreCase = true) == true) "L" else "?"

    private fun JSONObject.permissionNames(): Set<String> =
        optJSONObject("permissions")?.keySetCompat().orEmpty().toSet()

    private fun Set<String>.countLocationPermissions(): Int =
        count { it.contains("LOCATION", ignoreCase = true) }

    private fun Set<String>.countStoragePermissions(): Int =
        count { it.contains("STORAGE", ignoreCase = true) || it.contains("READ_MEDIA", ignoreCase = true) || it.contains("WRITE_EXTERNAL", ignoreCase = true) }

    private fun Set<String>.countSensorOrActivityPermissions(): Int =
        count { it.contains("BODY_SENSORS", ignoreCase = true) || it.contains("ACTIVITY_RECOGNITION", ignoreCase = true) || it.contains("HIGH_SAMPLING_RATE_SENSORS", ignoreCase = true) }

    private fun String.isHealthConnectPermission(): Boolean =
        startsWith("android.permission.health.", ignoreCase = true)

    private fun JSONObject.countDangerousPermissions(): Int {
        val permissions = optJSONObject("permissions") ?: return 0
        return permissions.keySetCompat().count { permission ->
            permissions.optJSONObject(permission)?.optString("status", "").equals("dangerous", ignoreCase = true)
        }
    }

    private fun JSONObject.totalFindingsBySeverity(severity: String): Int =
        countManifestFindingsBySeverity(severity) +
                countCodeFindingsBySeverity(severity) +
                countCertificateFindingsBySeverity(severity) +
                countBinaryFindingsBySeverity(severity)

    private fun JSONObject.countManifestFindingsBySeverity(severity: String): Int =
        manifestFindings().count { it.optString("severity", "").equals(severity, ignoreCase = true) }

    private fun JSONObject.countCodeFindingsBySeverity(severity: String): Int {
        val findings = optJSONObject("code_analysis")?.optJSONObject("findings") ?: return 0
        return findings.keySetCompat().count { key ->
            findings.optJSONObject(key)
                ?.optJSONObject("metadata")
                ?.optString("severity", "")
                ?.equals(severity, ignoreCase = true) == true
        }
    }

    private fun JSONObject.countCertificateFindingsBySeverity(severity: String): Int =
        optJSONObject("certificate_analysis")
            ?.optJSONObject("certificate_summary")
            ?.optInt(severity.lowercase(), 0)
            ?: 0

    private fun JSONObject.countBinaryFindingsBySeverity(severity: String): Int {
        val binaries = optJSONArray("binary_analysis") ?: return 0
        var count = 0
        for (index in 0 until binaries.length()) {
            val binary = binaries.optJSONObject(index) ?: continue
            binary.keySetCompat().forEach { key ->
                val item = binary.optJSONObject(key)
                if (item?.optString("severity", "")?.equals(severity, ignoreCase = true) == true) {
                    count += 1
                }
            }
        }
        return count
    }

    private fun JSONObject.manifestFindings(): List<JSONObject> {
        val array = optJSONObject("manifest_analysis")?.optJSONArray("manifest_findings") ?: return emptyList()
        return List(array.length()) { index -> array.optJSONObject(index) }.filterNotNull()
    }

    private fun JSONObject.hasCleartextTraffic(): Boolean =
        manifestFindings().any {
            it.optString("rule", "").contains("clear_text", ignoreCase = true) ||
                    it.optString("title", "").contains("clear text", ignoreCase = true)
        }

    private fun JSONObject.hasAllowBackup(): Boolean =
        manifestFindings().any {
            it.optString("rule", "").contains("allowbackup", ignoreCase = true) ||
                    it.optString("title", "").contains("allowBackup=true", ignoreCase = true)
        }

    private fun JSONObject.countExportedComponents(): Int =
        manifestFindings().count {
            it.optString("rule", "").contains("exported", ignoreCase = true) ||
                    it.optString("title", "").contains("exported=true", ignoreCase = true)
        }.takeIf { it > 0 } ?: optInt("exported_count", 0)

    private fun JSONObject.hasCodeFinding(key: String): Boolean =
        optJSONObject("code_analysis")?.optJSONObject("findings")?.has(key) == true

    private fun JSONObject.countCodeFindingsMatching(term: String): Int {
        val findings = optJSONObject("code_analysis")?.optJSONObject("findings") ?: return 0
        return findings.keySetCompat().count { key ->
            val item = findings.optJSONObject(key)
            key.contains(term, ignoreCase = true) ||
                    item?.optString("title", "")?.contains(term, ignoreCase = true) == true ||
                    item?.optJSONObject("metadata")?.optString("description", "")?.contains(term, ignoreCase = true) == true
        }
    }

    private fun JSONObject.countWeakCryptoFindings(): Int {
        val terms = listOf("crypto", "cipher", "ecb", "cbc", "random", "md5", "sha1")
        val findings = optJSONObject("code_analysis")?.optJSONObject("findings") ?: return 0
        return findings.keySetCompat().count { key ->
            val metadata = findings.optJSONObject(key)?.optJSONObject("metadata")
            val text = listOf(
                key,
                metadata?.optString("description", "").orEmpty(),
                metadata?.optString("cwe", "").orEmpty(),
            ).joinToString(" ")
            terms.any { text.contains(it, ignoreCase = true) }
        }
    }

    private fun JSONObject.countStackCanaryHighFindings(): Int {
        val binaries = optJSONArray("binary_analysis") ?: return 0
        var count = 0
        for (index in 0 until binaries.length()) {
            val canary = binaries.optJSONObject(index)?.optJSONObject("stack_canary")
            if (canary?.optString("severity", "")?.equals("high", ignoreCase = true) == true) {
                count += 1
            }
        }
        return count
    }

    private fun JSONObject.trackerCount(): Int {
        val trackers = opt("trackers")
        return when (trackers) {
            is JSONObject -> trackers.optInt("detected_trackers", trackers.optJSONArray("trackers")?.length() ?: trackers.length())
            is JSONArray -> trackers.length()
            else -> 0
        }
    }

    private fun JSONObject.collectionSize(name: String): Int {
        if (!has(name) || isNull(name)) return 0
        return when (val value = opt(name)) {
            is JSONArray -> value.length()
            is JSONObject -> value.length()
            is String -> if (value.isBlank()) 0 else 1
            else -> 0
        }
    }

    private fun JSONObject.httpUrlCount(): Int =
        stringCollection("urls").count { it.startsWith("http://", ignoreCase = true) }

    private fun JSONObject.stringCollection(name: String): List<String> {
        if (!has(name) || isNull(name)) return emptyList()
        return when (val value = opt(name)) {
            is JSONArray -> List(value.length()) { index -> value.optString(index) }.filter { it.isNotBlank() }
            is JSONObject -> value.keySetCompat()
            is String -> listOf(value).filter { it.isNotBlank() }
            else -> emptyList()
        }
    }

    private fun JSONObject.importantFindings(side: String): List<TechnicalFinding> {
        val manifest = manifestFindings()
            .filter { it.optString("severity", "").equals("high", true) || it.optString("rule", "").contains("clear_text", true) || it.optString("rule", "").contains("allowbackup", true) }
            .map {
                TechnicalFinding(
                    title = it.optString("title", it.optString("name", "Hallazgo de manifest")),
                    severity = it.optString("severity", "warning"),
                    affectedSide = side,
                    category = "Manifest",
                    summary = it.optNullableString("description"),
                    mastgRelation = manifestRuleToMastg(it.optString("rule", "")),
                    relationType = if (manifestRuleToMastg(it.optString("rule", "")) != null) "direct" else "inferred",
                )
            }

        val codeFindings = optJSONObject("code_analysis")?.optJSONObject("findings")
        val code = codeFindings?.keySetCompat().orEmpty()
            .mapNotNull { key ->
                val item = codeFindings?.optJSONObject(key) ?: return@mapNotNull null
                val metadata = item.optJSONObject("metadata")
                val severity = metadata?.optString("severity", "info") ?: "info"
                val isImportant = severity.equals("high", true) ||
                        key.contains("logging", true) ||
                        key.contains("external", true) ||
                        key.contains("webview", true) ||
                        key.contains("crypto", true) ||
                        key.contains("random", true)
                if (!isImportant) return@mapNotNull null
                TechnicalFinding(
                    title = key.replace('_', ' ').replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() },
                    severity = severity,
                    affectedSide = side,
                    category = "Código",
                    summary = metadata?.optNullableString("description"),
                    detail = metadata?.optNullableString("ref"),
                    mastgRelation = codeRuleToMastg(key),
                    relationType = if (codeRuleToMastg(key) != null) "direct/inferred" else "inferred",
                    masvs = metadata?.optNullableString("masvs"),
                    cwe = metadata?.optNullableString("cwe"),
                )
            }.orEmpty()

        val binary = countStackCanaryHighFindings().takeIf { it > 0 }?.let {
            listOf(
                TechnicalFinding(
                    title = "Binarios sin Stack Canary",
                    severity = "high",
                    affectedSide = side,
                    category = "Hardening nativo",
                    summary = "$it librerías nativas no declaran protección Stack Canary.",
                    relationType = "inferred",
                )
            )
        }.orEmpty()

        return (manifest + code + binary).take(12)
    }

    private fun manifestRuleToMastg(rule: String): String? = when {
        rule.contains("clear_text", ignoreCase = true) -> "MASTG-TEST-0235"
        rule.contains("allowbackup", ignoreCase = true) -> "MASTG-TEST-0262"
        else -> null
    }

    private fun codeRuleToMastg(rule: String): String? = when {
        rule.contains("logging", ignoreCase = true) -> "MASTG-TEST-0231"
        rule.contains("external", ignoreCase = true) -> "MASTG-TEST-0202"
        else -> null
    }

    private fun severityRank(value: String?): Int = when (value?.lowercase()) {
        "critical", "high" -> 0
        "warning", "medium" -> 1
        else -> 2
    }

    private fun Boolean.toIntFlag(): Int = if (this) 1 else 0

    private fun JSONObject.optNullableIntFromString(name: String): Int? {
        if (!has(name) || isNull(name)) return null
        return optString(name).toIntOrNull() ?: optInt(name)
    }

    private fun JSONObject.keySetCompat(): List<String> {
        val result = mutableListOf<String>()
        val iterator = keys()
        while (iterator.hasNext()) {
            result += iterator.next()
        }
        return result
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

    private fun JSONObject.optNullableFloatAny(vararg names: String): Float? {
        names.forEach { name ->
            if (has(name) && !isNull(name)) {
                return optDouble(name).toFloat()
            }
        }
        return null
    }

    private fun JSONObject.optNullableStringAny(vararg names: String): String? {
        names.forEach { name ->
            if (has(name) && !isNull(name)) {
                val value = optString(name)
                if (value.isNotBlank()) return value
            }
        }
        return null
    }

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

private fun JSONObject.optIntOrNull(name: String): Int? = if (has(name) && !isNull(name)) optInt(name) else null
