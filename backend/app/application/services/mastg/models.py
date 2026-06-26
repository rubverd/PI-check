from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MastgEvaluationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    ERROR = "ERROR"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EXECUTED = "NOT_EXECUTED"


@dataclass(frozen=True)
class MastgEvaluationContext:
    id_app: str
    version: str
    id_mastg: str | None = None
    mobsf_json: dict[str, Any] | None = None
    apk_path: Path | None = None
    report_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_mobsf_json(self) -> bool:
        return isinstance(self.mobsf_json, dict) and bool(self.mobsf_json)

    @property
    def has_apk(self) -> bool:
        return self.apk_path is not None and self.apk_path.exists() and self.apk_path.is_file()


@dataclass
class MastgRuleResult:
    status: MastgEvaluationStatus
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    recommendation: str | None = None
    error: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def pass_(
        cls,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        recommendation: str | None = None,
    ) -> MastgRuleResult:
        return cls(
            status=MastgEvaluationStatus.PASS,
            summary=summary,
            details=details or {},
            evidence=evidence or [],
            recommendation=recommendation,
        )

    @classmethod
    def fail(
        cls,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        recommendation: str | None = None,
    ) -> MastgRuleResult:
        return cls(
            status=MastgEvaluationStatus.FAIL,
            summary=summary,
            details=details or {},
            evidence=evidence or [],
            recommendation=recommendation,
        )

    @classmethod
    def review(
        cls,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        recommendation: str | None = None,
    ) -> MastgRuleResult:
        return cls(
            status=MastgEvaluationStatus.REVIEW,
            summary=summary,
            details=details or {},
            evidence=evidence or [],
            recommendation=recommendation,
        )

    @classmethod
    def not_evaluable(
        cls,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> MastgRuleResult:
        return cls(
            status=MastgEvaluationStatus.NOT_EVALUABLE,
            summary=summary,
            details=details or {},
            evidence=evidence or [],
        )

    @classmethod
    def error_result(
        cls,
        summary: str,
        *,
        error: str,
        details: dict[str, Any] | None = None,
        evidence: list[dict[str, Any]] | None = None,
    ) -> MastgRuleResult:
        return cls(
            status=MastgEvaluationStatus.ERROR,
            summary=summary,
            details=details or {},
            evidence=evidence or [],
            error=error,
        )
