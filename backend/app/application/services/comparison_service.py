from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import AppAnalysisService
from app.domain.entities.comparison_result import ComparisonResult
from app.schemas.comparisons import ComparisonRequest


@dataclass
class ComparisonExecutionResult:
    comparison_id: str
    status: str
    message: str
    messages: list[str]
    comparison: ComparisonResult


class ComparisonService:
    def __init__(self, db: Session):
        self.db = db
        self.app_analysis_service = AppAnalysisService(db)

    def create_comparison(
        self,
        request: ComparisonRequest,
    ) -> ComparisonExecutionResult:
        comparison_id = str(uuid4())

        messages: list[str] = [
            f"Solicitud de comparación creada con identificador {comparison_id}.",
            f"Aplicación A seleccionada: {request.app_a.title}.",
            f"Aplicación B seleccionada: {request.app_b.title}.",
        ]

        report_a, messages_a = self.app_analysis_service.ensure_version_report_with_mobsf(
            selected_app=request.app_a,
            comparison_id=comparison_id,
        )

        messages.extend(messages_a)

        report_b, messages_b = self.app_analysis_service.ensure_version_report_with_mobsf(
            selected_app=request.app_b,
            comparison_id=comparison_id,
        )

        messages.extend(messages_b)

        comparison = ComparisonResult(
            app_a=report_a,
            app_b=report_b,
            id_indice_aplicado=None,
        )

        messages.append("Comparativa creada en memoria correctamente.")

        return ComparisonExecutionResult(
            comparison_id=comparison_id,
            status="completed",
            message="Comparativa generada correctamente.",
            messages=messages,
            comparison=comparison,
        )