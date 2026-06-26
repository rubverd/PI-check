from __future__ import annotations

from collections import Counter
from typing import Any

from app.application.services.mastg.models import MastgEvaluationStatus


class MastgScoreService:
    """
    Calcula score y cobertura sin pesos.

    score = PASS / (PASS + FAIL + REVIEW)
    coverage = (PASS + FAIL + REVIEW) / total
    """

    SCORABLE_STATUSES = {
        MastgEvaluationStatus.PASS.value,
        MastgEvaluationStatus.FAIL.value,
        MastgEvaluationStatus.REVIEW.value,
    }

    ALL_STATUSES = [status.value for status in MastgEvaluationStatus]

    def calculate(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(results)
        status_counter = Counter(str(item.get("resultado")) for item in results)

        pass_count = status_counter[MastgEvaluationStatus.PASS.value]
        fail_count = status_counter[MastgEvaluationStatus.FAIL.value]
        review_count = status_counter[MastgEvaluationStatus.REVIEW.value]

        scorable_total = pass_count + fail_count + review_count

        score = None
        score_percent = None

        if scorable_total > 0:
            score = pass_count / scorable_total
            score_percent = round(score * 100, 2)

        coverage = 0.0
        coverage_percent = 0.0

        if total > 0:
            coverage = scorable_total / total
            coverage_percent = round(coverage * 100, 2)

        status_summary = {
            status: status_counter[status]
            for status in self.ALL_STATUSES
        }

        return {
            "score": score,
            "score_percent": score_percent,
            "coverage": coverage,
            "coverage_percent": coverage_percent,
            "total_tests": total,
            "scorable_tests": scorable_total,
            "status_summary": status_summary,
        }
