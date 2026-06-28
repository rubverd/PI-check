from __future__ import annotations

import zipfile

from app.application.services.mastg.evaluators.base import (
    scan_apk_dex_patterns,
    summarize_findings,
)
from app.application.services.mastg.models import (
    MastgEvaluationContext,
    MastgRuleResult,
)


TLS_REVIEW_PATTERNS = {
    "trust_manager": [
        "javax/net/ssl/X509TrustManager",
        "checkServerTrusted",
        "checkClientTrusted",
        "getAcceptedIssuers",
    ],
    "hostname_verifier": [
        "javax/net/ssl/HostnameVerifier",
        "ALLOW_ALL_HOSTNAME_VERIFIER",
        "AllowAllHostnameVerifier",
    ],
    "ssl_error_bypass": [
        "android/webkit/SslErrorHandler",
        "onReceivedSslError",
    ],
    "custom_ssl_context": [
        "javax/net/ssl/SSLContext",
        "TrustAll",
        "trustAll",
        "InsecureTrustManager",
        "NaiveTrustManager",
    ],
}


OBSOLETE_TLS_PROTOCOL_PATTERNS = {
    "obsolete_tls_protocol": [
        "SSLv3",
        "TLSv1.0",
        "TLSv1.1",
    ],
}


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_apk:
        return MastgRuleResult.not_evaluable(
            "No hay APK disponible para ejecutar el escáner estático de TLS inseguro."
        )

    try:
        tls_review_findings = scan_apk_dex_patterns(context.apk_path, TLS_REVIEW_PATTERNS)
        obsolete_protocol_findings = scan_apk_dex_patterns(
            context.apk_path,
            OBSOLETE_TLS_PROTOCOL_PATTERNS,
        )
    except zipfile.BadZipFile as exc:
        return MastgRuleResult.error_result(
            "El APK no es un ZIP válido y no se puede analizar.",
            error=str(exc),
        )

    details = {
        "apk_path": str(context.apk_path),
        "obsolete_protocol_findings": summarize_findings(obsolete_protocol_findings),
        "tls_review_findings": summarize_findings(tls_review_findings),
    }

    evidence = [
        {
            "category": category,
            "matches": matches[:20],
        }
        for category, matches in {**obsolete_protocol_findings, **tls_review_findings}.items()
    ]

    if obsolete_protocol_findings:
        return MastgRuleResult.fail(
            "Se han detectado referencias explícitas a protocolos TLS/SSL obsoletos.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Eliminar cualquier configuración que permita SSLv3, TLSv1.0 o TLSv1.1 "
                "y restringir las comunicaciones a versiones TLS modernas."
            ),
        )

    if tls_review_findings:
        return MastgRuleResult.review(
            "Se han detectado patrones genéricos de TLS personalizado; requieren revisión manual y no prueban por sí solos protocolos obsoletos.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Revisar manualmente el uso de X509TrustManager, HostnameVerifier, SSLContext "
                "y lógica de validación TLS."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han detectado patrones relevantes de TLS inseguro en los DEX del APK.",
        details=details,
    )