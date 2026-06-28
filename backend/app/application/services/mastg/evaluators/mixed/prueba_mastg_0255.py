from __future__ import annotations

import zipfile
from typing import Any

from app.application.services.mastg.evaluators.base import (
    limit_evidence,
    scan_apk_dex_patterns,
    summarize_findings,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


PRIVILEGE_PERMISSION_GROUPS = {
    "location": {
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_BACKGROUND_LOCATION",
    },
    "sensors_health": {
        "android.permission.ACTIVITY_RECOGNITION",
        "android.permission.BODY_SENSORS",
        "android.permission.BODY_SENSORS_BACKGROUND",
    },
    "contacts_calendar": {
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.READ_CALENDAR",
        "android.permission.WRITE_CALENDAR",
    },
    "media_camera_microphone": {
        "android.permission.CAMERA",
        "android.permission.RECORD_AUDIO",
        "android.permission.READ_MEDIA_AUDIO",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
    },
    "phone_sms": {
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_PHONE_NUMBERS",
        "android.permission.READ_SMS",
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
    },
    "storage": {
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
    },
    "nearby_devices": {
        "android.permission.BLUETOOTH_SCAN",
        "android.permission.BLUETOOTH_CONNECT",
        "android.permission.BLUETOOTH_ADVERTISE",
        "android.permission.UWB_RANGING",
    },
}

SENSITIVE_API_PATTERNS = {
    "location": [
        "android/location/LocationManager",
        "com/google/android/gms/location/FusedLocationProviderClient",
    ],
    "contacts": [
        "android/provider/ContactsContract",
    ],
    "calendar": [
        "android/provider/CalendarContract",
    ],
    "camera_microphone": [
        "android/hardware/Camera",
        "android/hardware/camera2",
        "android/media/MediaRecorder",
    ],
    "phone_sms": [
        "android/telephony/SmsManager",
        "android/telephony/TelephonyManager",
    ],
    "health_connect": [
        "androidx/health/connect/client/HealthConnectClient",
        "androidx/health/connect/client/permission/HealthPermission",
        "android/health/connect",
    ],
    "body_sensors": [
        "android/hardware/Sensor",
    ],
}


def _extract_permissions(mobsf_json: dict[str, Any]) -> list[str]:
    raw_permissions = mobsf_json.get("permissions")

    if isinstance(raw_permissions, dict):
        return [str(permission_name) for permission_name in raw_permissions.keys()]

    if isinstance(raw_permissions, list):
        permissions: list[str] = []

        for item in raw_permissions:
            if isinstance(item, dict):
                permissions.append(
                    str(
                        item.get("permission")
                        or item.get("name")
                        or item.get("id")
                        or ""
                    )
                )
            else:
                permissions.append(str(item))

        return [permission for permission in permissions if permission]

    return []


def _group_permissions(permissions: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}

    for group_name, group_permissions in PRIVILEGE_PERMISSION_GROUPS.items():
        matches = [
            permission
            for permission in permissions
            if permission in group_permissions
        ]

        if matches:
            grouped[group_name] = matches

    return grouped


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json and not context.has_apk:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON ni APK disponibles para evaluar minimización de privilegios."
        )

    permissions: list[str] = []
    grouped_permissions: dict[str, list[str]] = {}

    if context.has_mobsf_json:
        permissions = _extract_permissions(context.mobsf_json or {})
        grouped_permissions = _group_permissions(permissions)

    api_findings: dict[str, list[str]] = {}
    apk_error: str | None = None

    if context.has_apk:
        try:
            api_findings = scan_apk_dex_patterns(context.apk_path, SENSITIVE_API_PATTERNS)
        except zipfile.BadZipFile as exc:
            apk_error = str(exc)

    details = {
        "permissions_count": len(permissions),
        "privilege_groups_count": len(grouped_permissions),
        "privilege_groups": grouped_permissions,
        "api_findings": summarize_findings(api_findings),
        "apk_error": apk_error,
    }

    evidence = limit_evidence(
        [
            {
                "source": "permission_group",
                "group": group,
                "permissions": group_permissions,
            }
            for group, group_permissions in grouped_permissions.items()
        ]
        + [
            {
                "source": "sensitive_api",
                "category": category,
                "matches": matches[:20],
            }
            for category, matches in api_findings.items()
        ]
    )

    if apk_error and not context.has_mobsf_json:
        return MastgRuleResult.error_result(
            "El APK no es un ZIP válido y no se puede analizar.",
            error=apk_error,
        )

    if grouped_permissions or api_findings:
        return MastgRuleResult.review(
            "Se han detectado permisos o APIs sensibles que requieren revisión de minimización de privilegios.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Comprobar si cada permiso/API sensible es estrictamente necesario para la finalidad "
                "de la aplicación y valorar alternativas más respetuosas con la privacidad."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado grupos de permisos ni APIs sensibles relevantes para minimización de privilegios.",
        details=details,
    )