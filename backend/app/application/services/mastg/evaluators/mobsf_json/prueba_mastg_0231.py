from __future__ import annotations

from app.application.services.mastg.models import (
    MastgEvaluationContext,
    MastgEvaluationStatus,
    MastgRuleResult,
)


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    return MastgRuleResult(
        status=MastgEvaluationStatus.NOT_EXECUTED,
        summary="Logging: evaluador pendiente de implementar.",
        details={
            "id_mastg": "MASTG-TEST-0231",
            "reason": "Evaluador MobSF JSON pendiente de implementar para evidencias de logging sensible.",
            "id_app": context.id_app,
            "version": context.version,
        },
        evidence=[],
        recommendation="Implementar este evaluador en una iteración posterior del motor MASTG/PI-check.",
    )
