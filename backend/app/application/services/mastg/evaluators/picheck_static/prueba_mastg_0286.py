from __future__ import annotations

from app.application.services.mastg.evaluators.base import (
    iter_strings,
    limit_evidence,
    walk_items,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


USER_CA_PATTERNS = (
    'certificates src="user"',
    "certificates src='user'",
    "certificates src=user",
    'src="user"',
    "src='user'",
    "src=user",
)

TRUST_ANCHOR_PATTERNS = (
    "trust-anchors",
    "trust anchors",
    "trustanchors",
)

DEBUG_OVERRIDE_PATTERNS = (
    "debug-overrides",
    "debug overrides",
    "debugoverrides",
)


def _contains_user_ca(text: str) -> bool:
    lowered = text.lower()
    normalized = lowered.replace(" ", "")

    if any(pattern.replace(" ", "") in normalized for pattern in USER_CA_PATTERNS):
        return True

    return "user" in lowered and any(pattern.replace(" ", "") in normalized for pattern in TRUST_ANCHOR_PATTERNS)


def _is_debug_context(text: str) -> bool:
    lowered = text.lower()
    normalized = lowered.replace(" ", "")

    return any(pattern.replace(" ", "") in normalized for pattern in DEBUG_OVERRIDE_PATTERNS)


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar confianza en CAs de usuario."
        )

    mobsf_json = context.mobsf_json or {}

    user_ca_evidence: list[dict[str, object]] = []
    debug_user_ca_evidence: list[dict[str, object]] = []

    for key, value in walk_items(mobsf_json):
        joined = f"{key}: {value}"

        if _contains_user_ca(joined):
            item = {
                "source": "json_item",
                "key": key,
                "value": str(value)[:500],
            }

            if _is_debug_context(joined):
                debug_user_ca_evidence.append(item)
            else:
                user_ca_evidence.append(item)

    for text in iter_strings(mobsf_json):
        if _contains_user_ca(text):
            item = {
                "source": "json_text",
                "text": text[:500],
            }

            if _is_debug_context(text):
                debug_user_ca_evidence.append(item)
            else:
                user_ca_evidence.append(item)

    details = {
        "user_ca_evidence_count": len(user_ca_evidence),
        "debug_user_ca_evidence_count": len(debug_user_ca_evidence),
    }

    evidence = limit_evidence(
        [
            {
                "type": "user_ca_release_or_unknown",
                **item,
            }
            for item in user_ca_evidence
        ]
        + [
            {
                "type": "user_ca_debug_override",
                **item,
            }
            for item in debug_user_ca_evidence
        ]
    )

    if user_ca_evidence:
        return MastgRuleResult.fail(
            "Se han detectado evidencias de confianza en CAs de usuario fuera de un contexto debug claro.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Eliminar trust-anchors con certificates src=\"user\" en configuración de release. "
                "Limitar certificados de usuario únicamente a debug-overrides cuando sea imprescindible."
            ),
        )

    if debug_user_ca_evidence:
        return MastgRuleResult.review(
            "Se han detectado CAs de usuario en contexto debug; requiere verificar que no aplica a builds de producción.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Confirmar que la configuración con CAs de usuario solo está disponible en builds debug "
                "y no en artefactos de producción."
            ),
        )

    return MastgRuleResult.pass_(
        "No se han encontrado evidencias de confianza en CAs de usuario en el informe MobSF.",
        details=details,
    )