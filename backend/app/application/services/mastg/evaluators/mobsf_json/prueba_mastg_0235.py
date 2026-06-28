from __future__ import annotations

from app.application.services.mastg.evaluators.base import iter_strings, walk_items
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


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar tráfico cleartext."
        )

    mobsf_json = context.mobsf_json or {}

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

    details = {
        "cleartext_evidence_count": len(explicit_evidence),
    }

    if explicit_evidence:
        return MastgRuleResult.fail(
            "El informe MobSF contiene evidencias de tráfico cleartext permitido o habilitado.",
            details=details,
            evidence=explicit_evidence[:30],
            recommendation=(
                "Deshabilitar tráfico HTTP mediante AndroidManifest/network security config "
                "y usar HTTPS en todos los canales de comunicación."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han encontrado evidencias de tráfico cleartext habilitado en el JSON MobSF.",
        details=details,
    )