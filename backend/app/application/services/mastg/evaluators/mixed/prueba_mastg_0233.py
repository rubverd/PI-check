from __future__ import annotations

from app.application.services.mastg.evaluators.base import (
    extract_http_urls,
    is_public_http_url,
    limit_evidence,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para buscar URLs HTTP."
        )

    urls = extract_http_urls(context.mobsf_json or {})

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

    details = {
        "total_http_urls": len(urls),
        "public_http_urls_count": len(public_http_urls),
        "ignored_http_urls_count": len(ignored_urls),
        "ignored_http_urls": ignored_urls[:50],
    }

    evidence = limit_evidence(
        [
            {
                "url": url,
                "reason": "public_http_url",
            }
            for url in public_http_urls
        ]
    )

    if public_http_urls:
        return MastgRuleResult.fail(
            "Se han detectado URLs HTTP públicas en evidencias MobSF tras aplicar filtrado PI-check.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Sustituir endpoints HTTP públicos por HTTPS y revisar si esas URLs pueden "
                "transportar datos personales o de salud."
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
