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
            "No hay informe MobSF JSON disponible para buscar URLs HTTP."
        )

    mobsf_json = context.mobsf_json or {}

    urls = extract_http_urls(mobsf_json)

    public_http_urls = [
        url
        for url in urls
        if is_public_http_url(url)
    ]

    ignored_urls = [
        url
        for url in urls
        if url not in public_http_urls
    ]

    cleartext_evidence = _collect_cleartext_evidence(mobsf_json)

    details = {
        "total_http_urls": len(urls),
        "public_http_urls_count": len(public_http_urls),
        "ignored_http_urls_count": len(ignored_urls),
        "ignored_http_urls": ignored_urls[:50],
        "cleartext_evidence_count": len(cleartext_evidence),
    }

    evidence = limit_evidence(
        [
            {
                "source": "public_http_url",
                "url": url,
                "reason": "public_http_url",
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
    )

    if public_http_urls and cleartext_evidence:
        return MastgRuleResult.fail(
            "Se han detectado URLs HTTP públicas y evidencias de tráfico cleartext permitido.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Sustituir endpoints HTTP públicos por HTTPS y deshabilitar tráfico cleartext "
                "mediante AndroidManifest o Network Security Config."
            ),
        )

    if public_http_urls:
        return MastgRuleResult.review(
            "Se han detectado URLs HTTP públicas en evidencias MobSF, pero no se confirma automáticamente su uso en tráfico real.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar si estas URLs se usan en comunicaciones reales y sustituirlas por HTTPS cuando proceda."
            ),
        )

    if ignored_urls:
        return MastgRuleResult.pass_(
            "Solo se han encontrado URLs HTTP ignoradas por reglas PI-check, como esquemas Android, localhost o direcciones privadas.",
            details=details,
        )

    return MastgRuleResult.pass_(
        "No se han encontrado URLs HTTP en las evidencias del informe MobSF.",
        details=details,
    )