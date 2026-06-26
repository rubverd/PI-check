from __future__ import annotations

from app.application.services.mastg.models import (
    MastgEvaluationContext,
    MastgEvaluationStatus,
    MastgRuleResult,
)


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    return MastgRuleResult(
        status=MastgEvaluationStatus.NOT_EXECUTED,
        summary="Reglas backup PI-check: evaluador pendiente de implementar.",
        details={
            "id_mastg": "PI-CHECK-BACKUP-RULES",
            "reason": "Prueba propia PI-check pendiente de implementar para reglas de backup.",
            "id_app": context.id_app,
            "version": context.version,
        },
        evidence=[],
        recommendation="Implementar este evaluador en una iteración posterior del motor MASTG/PI-check.",
    )
