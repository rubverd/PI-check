from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.domain.value_objects.mastg_result_status import MastgResultStatus


@dataclass(frozen=True)
class MastgTestRunResult:
    id_mastg: str
    status: MastgResultStatus
    evidence: dict[str, object] = field(default_factory=dict)
    message: str | None = None


class MastgLiteTest(Protocol):
    id_prueba: str
    referencia_mastg: str
    nombre: str
    descripcion: str
    owasp_category: str | None

    def run(self, context: object) -> MastgTestRunResult:
        """Ejecuta una prueba MASTG-lite estática."""
