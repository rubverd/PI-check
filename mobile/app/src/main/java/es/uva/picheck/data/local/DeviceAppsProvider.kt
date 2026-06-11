package es.uva.picheck.data.local

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import es.uva.picheck.data.model.DeviceAppInfo

fun getInstalledDeviceApps(context: Context): List<DeviceAppInfo> {
    val packageManager = context.packageManager
    val launcherIntent = Intent(Intent.ACTION_MAIN).apply {
        addCategory(Intent.CATEGORY_LAUNCHER)
    }

    val launcherActivities = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        packageManager.queryIntentActivities(
            launcherIntent,
            PackageManager.ResolveInfoFlags.of(0),
        )
    } else {
        @Suppress("DEPRECATION")
        packageManager.queryIntentActivities(launcherIntent, 0)
    }

    return launcherActivities
        .mapNotNull { resolveInfo ->
            val applicationInfo = resolveInfo.activityInfo?.applicationInfo ?: return@mapNotNull null
            val name = applicationInfo.loadLabel(packageManager).toString()
            val sourceDir = applicationInfo.sourceDir ?: return@mapNotNull null

            DeviceAppInfo(
                name = name.ifBlank { applicationInfo.packageName },
                packageName = applicationInfo.packageName,
                sourceDir = sourceDir,
                splitSourceDirs = applicationInfo.splitSourceDirs?.toList().orEmpty(),
            )
        }
        .distinctBy { it.packageName }
        .sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { it.name })
}
