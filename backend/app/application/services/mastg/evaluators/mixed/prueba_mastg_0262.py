from __future__ import annotations

from app.application.services.mastg.models import (
    MastgEvaluationContext,
    MastgEvaluationStatus,
    MastgRuleResult,
)


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    return MastgRuleResult(
        status=MastgEvaluationStatus.NOT_EXECUTED,
        summary="Backup: evaluador pendiente de implementar.",
        details={
            "id_mastg": "MASTG-TEST-0262",
            "reason": "Evaluador mixto pendiente de implementar para configuración de backup.",
            "id_app": context.id_app,
            "version": context.version,
        },
        evidence=[],
        recommendation="Implementar este evaluador en una iteración posterior del motor MASTG/PI-check.",
    )
