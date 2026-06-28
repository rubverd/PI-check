from __future__ import annotations

from typing import Any

from app.application.services.mastg.evaluators.base import (
    iter_strings,
    limit_evidence,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


EXTERNAL_STORAGE_PERMISSIONS = {
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_AUDIO",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
}

EXTERNAL_STORAGE_PATTERNS = (
    "getexternalstoragedirectory",
    "getexternalfilesdir",
    "getexternalcachedir",
    "external storage",
    "externalstorage",
    "mediastore",
    "environment.external_storage",
    "write_external_storage",
    "read_external_storage",
    "manage_external_storage",
    "read_media_images",
    "read_media_video",
    "read_media_audio",
)

HIGH_RISK_TEXT_PATTERNS = (
    "sensitive data in external storage",
    "sensitive information in external storage",
    "unencrypted data in external storage",
    "external storage contains sensitive",
    "datos sensibles en almacenamiento externo",
    "información sensible en almacenamiento externo",
)


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


def _permission_name(permission: dict[str, Any]) -> str:
    return str(
        permission.get("permission")
        or permission.get("name")
        or permission.get("id")
        or ""
    ).strip()


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar almacenamiento externo."
        )

    mobsf_json = context.mobsf_json or {}

    permissions = _extract_permissions(mobsf_json)
    storage_permissions = [
        permission
        for permission in permissions
        if _permission_name(permission) in EXTERNAL_STORAGE_PERMISSIONS
    ]

    text_matches: list[dict[str, str]] = []
    high_risk_matches: list[dict[str, str]] = []

    for text in iter_strings(mobsf_json):
        normalized = text.replace(" ", "").replace("_", "").lower()

        if any(pattern.replace(" ", "").replace("_", "") in normalized for pattern in EXTERNAL_STORAGE_PATTERNS):
            text_matches.append({"text": text[:500]})

        lowered = text.lower()
        if any(pattern in lowered for pattern in HIGH_RISK_TEXT_PATTERNS):
            high_risk_matches.append({"text": text[:500]})

    details = {
        "storage_permissions_count": len(storage_permissions),
        "storage_permissions": [_permission_name(item) for item in storage_permissions],
        "storage_text_matches_count": len(text_matches),
        "high_risk_matches_count": len(high_risk_matches),
    }

    evidence = limit_evidence(
        [
            {
                "source": "permission",
                "permission": _permission_name(permission),
                "metadata": permission,
            }
            for permission in storage_permissions
        ]
        + [
            {
                "source": "mobsf_text",
                **match,
            }
            for match in text_matches
        ]
        + [
            {
                "source": "high_risk_mobsf_text",
                **match,
            }
            for match in high_risk_matches
        ]
    )

    if high_risk_matches:
        return MastgRuleResult.fail(
            "El informe MobSF contiene indicios explícitos de datos sensibles en almacenamiento externo.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Evitar almacenar datos personales o de salud en almacenamiento externo compartido. "
                "Si resulta imprescindible, aplicar cifrado y controles de acceso adecuados."
            ),
        )

    if storage_permissions or text_matches:
        return MastgRuleResult.review(
            "Se han detectado permisos o APIs relacionados con almacenamiento externo; requiere revisión manual.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Comprobar si la aplicación escribe datos personales o de salud en almacenamiento externo "
                "y si dichos datos se protegen mediante cifrado."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado permisos ni evidencias relevantes de almacenamiento externo en el informe MobSF.",
        details=details,
    )