from __future__ import annotations

import zipfile

from app.application.services.mastg.evaluators.base import (
    scan_apk_dex_patterns,
    summarize_findings,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


INSECURE_TLS_PATTERNS = {
    "trust_manager": [
        "javax/net/ssl/X509TrustManager",
        "checkServerTrusted",
        "checkClientTrusted",
        "getAcceptedIssuers",
    ],
    "hostname_verifier": [
        "javax/net/ssl/HostnameVerifier",
        "verify",
        "ALLOW_ALL_HOSTNAME_VERIFIER",
        "AllowAllHostnameVerifier",
    ],
    "ssl_error_bypass": [
        "android/webkit/SslErrorHandler",
        "onReceivedSslError",
        "proceed",
    ],
    "insecure_ssl_context": [
        "javax/net/ssl/SSLContext",
        "TrustAll",
        "trustAll",
        "InsecureTrustManager",
        "NaiveTrustManager",
    ],
}


HIGH_CONFIDENCE_CATEGORIES = {
    "hostname_verifier",
    "ssl_error_bypass",
    "insecure_ssl_context",
}


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_apk:
        return MastgRuleResult.not_evaluable(
            "No hay APK disponible para ejecutar el escáner estático de TLS inseguro."
        )

    try:
        findings = scan_apk_dex_patterns(context.apk_path, INSECURE_TLS_PATTERNS)
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

    high_confidence = sorted(
        category
        for category in findings
        if category in HIGH_CONFIDENCE_CATEGORIES
    )

    details["high_confidence_categories"] = high_confidence

    if high_confidence:
        return MastgRuleResult.fail(
            "Se han detectado patrones de alto riesgo compatibles con validación TLS insegura.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar implementaciones personalizadas de TrustManager, HostnameVerifier "
                "y manejadores de errores SSL. No se deben aceptar certificados o hosts sin validación estricta."
            ),
        )

    if findings:
        return MastgRuleResult.review(
            "Se han detectado clases relacionadas con TLS personalizado, pero la evidencia no es concluyente.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar manualmente el uso de X509TrustManager, SSLContext y lógica de validación TLS."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado patrones relevantes de TLS inseguro en los DEX del APK.",
        details=details,
    )
