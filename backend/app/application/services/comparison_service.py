from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import AppAnalysisService
from app.application.services.app_registration_service import AppRegistrationService
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
        self.app_registration_service = AppRegistrationService(db)
        self.app_analysis_service = AppAnalysisService(db)

    def create_comparison(
        self,
        request: ComparisonRequest,
    ) -> ComparisonExecutionResult:
        comparison_id = str(uuid4())

        messages: list[str] = [
            f"[COMPARISON] Solicitud creada con identificador {comparison_id}.",
            f"[COMPARISON] Aplicación A seleccionada: {request.app_a.title}.",
            f"[COMPARISON] Aplicación B seleccionada: {request.app_b.title}.",
        ]

        prepared_by_app_id, registration_messages = (
            self.app_registration_service.prepare_apps_for_comparison(
                selected_apps=[request.app_a, request.app_b],
                comparison_id=comparison_id,
                download_apks=request.download_apks,
            )
        )

        messages.extend(registration_messages)

        prepared_a = prepared_by_app_id[request.app_a.app_id]
        prepared_b = prepared_by_app_id[request.app_b.app_id]

        report_a, messages_a = self.app_analysis_service.ensure_mobsf_report(
            prepared_app=prepared_a,
        )

        messages.extend(messages_a)

        report_b, messages_b = self.app_analysis_service.ensure_mobsf_report(
            prepared_app=prepared_b,
        )

        messages.extend(messages_b)

        comparison = ComparisonResult(
            app_a=report_a,
            app_b=report_b,
            id_indice_aplicado=None,
        )

        messages.append("[COMPARISON] Comparativa creada en memoria correctamente.")

        return ComparisonExecutionResult(
            comparison_id=comparison_id,
            status="completed",
            message="Comparativa generada correctamente.",
            messages=messages,
            comparison=comparison,
        )