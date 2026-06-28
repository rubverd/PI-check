from __future__ import annotations

from typing import Any

from app.application.services.mastg.evaluators.base import (
    extract_http_urls,
    is_public_http_url,
    iter_strings,
    limit_evidence,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


SENSITIVE_PERMISSION_HINTS = {
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.BODY_SENSORS",
    "android.permission.BODY_SENSORS_BACKGROUND",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_CALENDAR",
    "android.permission.READ_PHONE_STATE",
    "android.permission.READ_SMS",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
}

SENSITIVE_TEXT_HINTS = (
    "advertisingidclient",
    "advertising id",
    "location",
    "contactscontract",
    "calendarcontract",
    "healthconnect",
    "health connect",
    "bodysensors",
    "body_sensors",
    "telephonymanager",
    "smsmanager",
    "fusedlocationproviderclient",
)

EXPLICIT_LEAK_PATTERNS = (
    "pii leak",
    "personal information leak",
    "personally identifiable information",
    "sensitive data transmitted",
    "sensitive information transmitted",
    "insecure transmission of sensitive",
    "transmits sensitive data over http",
    "leakage of sensitive",
    "datos personales transmitidos",
    "fuga de datos personales",
)


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


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar exposición de PII en comunicaciones."
        )

    mobsf_json = context.mobsf_json or {}

    permissions = _extract_permissions(mobsf_json)
    sensitive_permissions = [
        permission
        for permission in permissions
        if permission in SENSITIVE_PERMISSION_HINTS
    ]

    urls = extract_http_urls(mobsf_json)
    public_http_urls = [
        url
        for url in urls
        if is_public_http_url(url)
    ]

    sensitive_text_matches: list[dict[str, str]] = []
    explicit_leak_matches: list[dict[str, str]] = []

    for text in iter_strings(mobsf_json):
        lowered = text.lower()

        if any(pattern in lowered for pattern in EXPLICIT_LEAK_PATTERNS):
            explicit_leak_matches.append({"text": text[:500]})

        normalized = lowered.replace("/", "").replace(".", "").replace("_", "")
        if any(hint.replace("/", "").replace(".", "").replace("_", "") in normalized for hint in SENSITIVE_TEXT_HINTS):
            sensitive_text_matches.append({"text": text[:500]})

    details = {
        "sensitive_permissions_count": len(sensitive_permissions),
        "sensitive_permissions": sensitive_permissions,
        "public_http_urls_count": len(public_http_urls),
        "sensitive_text_matches_count": len(sensitive_text_matches),
        "explicit_leak_matches_count": len(explicit_leak_matches),
    }

    evidence = limit_evidence(
        [
            {
                "source": "sensitive_permission",
                "permission": permission,
            }
            for permission in sensitive_permissions
        ]
        + [
            {
                "source": "public_http_url",
                "url": url,
            }
            for url in public_http_urls
        ]
        + [
            {
                "source": "sensitive_text",
                **match,
            }
            for match in sensitive_text_matches
        ]
        + [
            {
                "source": "explicit_leak_text",
                **match,
            }
            for match in explicit_leak_matches
        ]
    )

    if explicit_leak_matches:
        return MastgRuleResult.fail(
            "El informe MobSF contiene indicios explícitos de exposición o transmisión insegura de información sensible.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar las comunicaciones de red y comprobar que no se transmitan datos personales "
                "o de salud sin protección adecuada."
            ),
        )

    if public_http_urls and (sensitive_permissions or sensitive_text_matches):
        return MastgRuleResult.review(
            "Se han detectado indicios estáticos de datos sensibles junto con URLs HTTP públicas; requiere validación dinámica.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Realizar análisis dinámico de tráfico para confirmar si se transmiten datos personales "
                "o de salud y si están declarados correctamente."
            ),
        )

    if sensitive_permissions or sensitive_text_matches:
        return MastgRuleResult.review(
            "Se han detectado permisos o referencias a datos sensibles, pero no evidencia concluyente de exposición en red.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Validar mediante análisis dinámico si estos datos se transmiten y si la transmisión está justificada."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han encontrado indicios estáticos relevantes de exposición de PII en comunicaciones.",
        details=details,
    )