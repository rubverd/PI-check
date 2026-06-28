from __future__ import annotations

import zipfile

from app.application.services.mastg.evaluators.base import (
    scan_apk_dex_patterns,
    summarize_findings,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


SENSITIVE_API_PATTERNS = {
    "advertising_id": [
        "com/google/android/gms/ads/identifier/AdvertisingIdClient",
        "getAdvertisingIdInfo",
        "advertising_id",
    ],
    "location": [
        "android/location/LocationManager",
        "android/location/Location",
        "com/google/android/gms/location/FusedLocationProviderClient",
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "ACCESS_BACKGROUND_LOCATION",
    ],
    "contacts": [
        "android/provider/ContactsContract",
        "READ_CONTACTS",
        "WRITE_CONTACTS",
    ],
    "calendar": [
        "android/provider/CalendarContract",
        "READ_CALENDAR",
        "WRITE_CALENDAR",
    ],
    "camera_microphone": [
        "android/hardware/Camera",
        "android/hardware/camera2",
        "android/media/MediaRecorder",
        "RECORD_AUDIO",
        "CAMERA",
    ],
    "phone_sms": [
        "android/telephony/SmsManager",
        "android/telephony/TelephonyManager",
        "READ_PHONE_STATE",
        "READ_SMS",
        "SEND_SMS",
    ],
    "health_connect": [
        "androidx/health/connect/client/HealthConnectClient",
        "androidx/health/connect/client/permission/HealthPermission",
        "android/health/connect",
    ],
    "body_sensors": [
        "BODY_SENSORS",
        "BODY_SENSORS_BACKGROUND",
        "android/hardware/Sensor",
    ],
}


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_apk:
        return MastgRuleResult.not_evaluable(
            "No hay APK disponible para ejecutar el escáner estático de APIs sensibles."
        )

    try:
        findings = scan_apk_dex_patterns(context.apk_path, SENSITIVE_API_PATTERNS)
    except zipfile.BadZipFile as exc:
        return MastgRuleResult.error_result(
            "El APK no es un ZIP válido y no se puede analizar.",
            error=str(exc),
        )

    details = summarize_findings(findings)
    details["apk_path"] = str(context.apk_path)

    evidence = [
        {
            "category": category,
            "matches": matches[:20],
        }
        for category, matches in findings.items()
    ]

    if findings:
        return MastgRuleResult.review(
            "Se han detectado referencias a APIs o permisos sensibles en el bytecode del APK.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar si las APIs sensibles detectadas son necesarias para la finalidad "
                "mHealth declarada y si existe minimización de datos."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado referencias relevantes a APIs sensibles en los DEX del APK.",
        details=details,
    )