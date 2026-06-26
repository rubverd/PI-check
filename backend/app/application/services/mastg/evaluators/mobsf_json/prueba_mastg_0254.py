from __future__ import annotations

from typing import Any

from app.application.services.mastg.evaluators.base import limit_evidence
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


DANGEROUS_PERMISSION_NAMES = {
    "android.permission.ACCEPT_HANDOVER",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.ADD_VOICEMAIL",
    "android.permission.ANSWER_PHONE_CALLS",
    "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.BODY_SENSORS",
    "android.permission.BODY_SENSORS_BACKGROUND",
    "android.permission.CAMERA",
    "android.permission.GET_ACCOUNTS",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.PROCESS_OUTGOING_CALLS",
    "android.permission.READ_CALENDAR",
    "android.permission.READ_CALL_LOG",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_AUDIO",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_PHONE_NUMBERS",
    "android.permission.READ_PHONE_STATE",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_MMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.RECEIVE_WAP_PUSH",
    "android.permission.RECORD_AUDIO",
    "android.permission.SEND_SMS",
    "android.permission.USE_SIP",
    "android.permission.UWB_RANGING",
    "android.permission.WRITE_CALENDAR",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.WRITE_CONTACTS",
    "android.permission.WRITE_EXTERNAL_STORAGE",
}


def _extract_permissions(mobsf_json: dict[str, Any]) -> list[dict[str, Any]]:
    raw_permissions = mobsf_json.get("permissions")

    if isinstance(raw_permissions, dict):
        permissions: list[dict[str, Any]] = []

        for permission_name, metadata in raw_permissions.items():
            item = {"permission": permission_name}

            if isinstance(metadata, dict):
                item.update(metadata)
            else:
                item["raw"] = metadata

            permissions.append(item)

        return permissions

    if isinstance(raw_permissions, list):
        permissions = []

        for item in raw_permissions:
            if isinstance(item, dict):
                permissions.append(item)
            else:
                permissions.append({"permission": str(item)})

        return permissions

    return []


def _is_dangerous(permission: dict[str, Any]) -> bool:
    permission_name = str(
        permission.get("permission")
        or permission.get("name")
        or permission.get("id")
        or ""
    ).strip()

    if permission_name in DANGEROUS_PERMISSION_NAMES:
        return True

    joined_values = " ".join(str(value) for value in permission.values()).lower()

    return "dangerous" in joined_values


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar permisos peligrosos."
        )

    permissions = _extract_permissions(context.mobsf_json or {})
    dangerous_permissions = [
        permission
        for permission in permissions
        if _is_dangerous(permission)
    ]

    evidence = limit_evidence(
        [
            {
                "permission": permission.get("permission") or permission.get("name"),
                "status": permission.get("status"),
                "info": permission.get("info"),
                "description": permission.get("description"),
            }
            for permission in dangerous_permissions
        ]
    )

    details = {
        "total_permissions": len(permissions),
        "dangerous_permissions_count": len(dangerous_permissions),
        "dangerous_permissions": [
            item.get("permission") or item.get("name")
            for item in dangerous_permissions
        ],
    }

    if dangerous_permissions:
        return MastgRuleResult.review(
            "La aplicación declara permisos Android peligrosos. Requiere revisión de minimización y justificación funcional.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Verificar que cada permiso peligroso sea imprescindible para la finalidad "
                "de la aplicación y esté justificado en el contexto mHealth."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado permisos peligrosos en el informe MobSF.",
        details=details,
    )
