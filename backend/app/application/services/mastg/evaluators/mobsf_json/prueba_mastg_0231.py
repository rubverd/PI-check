from __future__ import annotations

import zipfile

from app.application.services.mastg.evaluators.base import (
    iter_strings,
    limit_evidence,
    scan_apk_dex_patterns,
    summarize_findings,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


LOGGING_API_PATTERNS = {
    "android_log": [
        "android/util/Log",
        "Log.d",
        "Log.e",
        "Log.i",
        "Log.v",
        "Log.w",
        "println",
    ],
    "java_logging": [
        "java/util/logging/Logger",
        "org/slf4j/Logger",
        "timber/log/Timber",
        "System.out",
        "System.err",
        "printStackTrace",
    ],
}

SENSITIVE_LOGGING_TEXT_PATTERNS = (
    "log sensitive",
    "logs sensitive",
    "sensitive data in logs",
    "sensitive information in logs",
    "password logged",
    "token logged",
    "credential logged",
    "pii in logs",
    "datos sensibles en logs",
    "información sensible en logs",
)


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_apk and not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay APK ni informe MobSF JSON disponibles para evaluar logging sensible."
        )

    findings: dict[str, list[str]] = {}
    apk_error: str | None = None

    if context.has_apk:
        try:
            findings = scan_apk_dex_patterns(context.apk_path, LOGGING_API_PATTERNS)
        except zipfile.BadZipFile as exc:
            apk_error = str(exc)

    mobsf_logging_matches: list[dict[str, str]] = []
    explicit_sensitive_logging_matches: list[dict[str, str]] = []

    if context.has_mobsf_json:
        for text in iter_strings(context.mobsf_json or {}):
            lowered = text.lower()

            if "log" in lowered or "logger" in lowered or "printstacktrace" in lowered:
                mobsf_logging_matches.append({"text": text[:500]})

            if any(pattern in lowered for pattern in SENSITIVE_LOGGING_TEXT_PATTERNS):
                explicit_sensitive_logging_matches.append({"text": text[:500]})

    details = {
        "apk_path": str(context.apk_path) if context.apk_path else None,
        "apk_error": apk_error,
        "dex_findings": summarize_findings(findings),
        "mobsf_logging_matches_count": len(mobsf_logging_matches),
        "explicit_sensitive_logging_matches_count": len(explicit_sensitive_logging_matches),
    }

    evidence = limit_evidence(
        [
            {
                "source": "dex_pattern",
                "category": category,
                "matches": matches[:20],
            }
            for category, matches in findings.items()
        ]
        + [
            {
                "source": "mobsf_logging_text",
                **match,
            }
            for match in mobsf_logging_matches
        ]
        + [
            {
                "source": "explicit_sensitive_logging_text",
                **match,
            }
            for match in explicit_sensitive_logging_matches
        ]
    )

    if apk_error and not context.has_mobsf_json:
        return MastgRuleResult.error_result(
            "El APK no es un ZIP válido y no se puede analizar.",
            error=apk_error,
        )

    if explicit_sensitive_logging_matches:
        return MastgRuleResult.fail(
            "Se han detectado indicios explícitos de información sensible registrada en logs.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Eliminar cualquier registro de credenciales, tokens, identificadores personales, "
                "datos de salud o información sensible."
            ),
        )

    if findings or mobsf_logging_matches:
        return MastgRuleResult.review(
            "Se han detectado APIs o evidencias de logging; requiere revisión para confirmar si registran datos sensibles.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar manualmente las llamadas de logging y evitar imprimir información personal, "
                "tokens, credenciales o datos de salud."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado evidencias relevantes de logging en el alcance analizado.",
        details=details,
    )