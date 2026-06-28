from __future__ import annotations

from app.application.services.mastg.evaluators.base import (
    extract_http_urls,
    is_public_http_url,
    iter_strings,
    limit_evidence,
    walk_items,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


CLEAR_TEXT_KEYS = {
    "usescleartexttraffic",
    "uses_cleartext_traffic",
    "cleartexttraffic",
    "cleartext_traffic",
    "clear_text_traffic",
}

RISK_TEXT_PATTERNS = (
    "usescleartexttraffic=true",
    "usescleartexttraffic=\"true\"",
    "android:usescleartexttraffic=\"true\"",
    "cleartext traffic is enabled",
    "clear text traffic is enabled",
    "cleartext traffic allowed",
    "clear text traffic allowed",
)


def _collect_cleartext_evidence(mobsf_json: dict) -> list[dict[str, object]]:
    explicit_evidence: list[dict[str, object]] = []

    for key, value in walk_items(mobsf_json):
        normalized_key = str(key).replace("-", "_").replace(" ", "_").lower()

        if normalized_key in CLEAR_TEXT_KEYS and value is True:
            explicit_evidence.append(
                {
                    "source": "json_key",
                    "key": key,
                    "value": value,
                }
            )

        if normalized_key in CLEAR_TEXT_KEYS and isinstance(value, str):
            if value.strip().lower() in {"true", "enabled", "allowed", "yes"}:
                explicit_evidence.append(
                    {
                        "source": "json_key",
                        "key": key,
                        "value": value,
                    }
                )

    for text in iter_strings(mobsf_json):
        normalized = text.replace(" ", "").lower()

        if any(pattern.replace(" ", "") in normalized for pattern in RISK_TEXT_PATTERNS):
            explicit_evidence.append(
                {
                    "source": "json_text",
                    "text": text[:500],
                }
            )

    return explicit_evidence


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para aplicar la regla contextual HTTP PI-check."
        )

    mobsf_json = context.mobsf_json or {}

    urls = extract_http_urls(mobsf_json)
    public_http_urls = [
        url
        for url in urls
        if is_public_http_url(url)
    ]

    ignored_http_urls = [
        url
        for url in urls
        if url not in public_http_urls
    ]

    cleartext_evidence = _collect_cleartext_evidence(mobsf_json)

    details = {
        "total_http_urls": len(urls),
        "public_http_urls_count": len(public_http_urls),
        "ignored_http_urls_count": len(ignored_http_urls),
        "cleartext_evidence_count": len(cleartext_evidence),
        "policy": "PI-check cruza URLs HTTP públicas con configuración cleartext para reducir falsos positivos.",
    }

    evidence = limit_evidence(
        [
            {
                "source": "public_http_url",
                "url": url,
            }
            for url in public_http_urls
        ]
        + [
            {
                "source": "cleartext_evidence",
                **item,
            }
            for item in cleartext_evidence
        ]
        + [
            {
                "source": "ignored_http_url",
                "url": url,
            }
            for url in ignored_http_urls[:20]
        ]
    )

    if public_http_urls and cleartext_evidence:
        return MastgRuleResult.fail(
            "Se han detectado URLs HTTP públicas y configuración que permite tráfico cleartext.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Sustituir URLs HTTP por HTTPS y deshabilitar tráfico cleartext en AndroidManifest "
                "o Network Security Config."
            ),
        )

    if public_http_urls:
        return MastgRuleResult.review(
            "Se han detectado URLs HTTP públicas, pero no se han encontrado evidencias claras de cleartext habilitado.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar si estas URLs se usan realmente y confirmar que no transportan datos personales o de salud."
            ),
        )

    if cleartext_evidence:
        return MastgRuleResult.review(
            "Se ha detectado configuración cleartext, aunque no se han encontrado URLs HTTP públicas en las evidencias MobSF.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar si la configuración cleartext es necesaria y restringirla por dominio si procede."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado URLs HTTP públicas ni configuración cleartext problemática en el informe MobSF.",
        details=details,
        evidence=evidence,
    )