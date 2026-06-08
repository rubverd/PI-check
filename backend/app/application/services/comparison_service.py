import logging
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import AppAnalysisService
from app.application.services.app_registration_service import (
    AppRegistrationService,
    _selected_app_key,
)
from app.domain.entities.comparison_result import ComparisonResult
from app.schemas.comparisons import ComparisonRequest

logger = logging.getLogger("pi-check")


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

        logger.info(
            "[COMPARISON] Solicitud recibida comparison_id=%s app_a=%s version_a=%s app_b=%s version_b=%s",
            comparison_id,
            request.app_a.app_id,
            request.app_a.selected_version or request.app_a.version,
            request.app_b.app_id,
            request.app_b.selected_version or request.app_b.version,
        )

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

        prepared_a = prepared_by_app_id[_selected_app_key(request.app_a)]
        prepared_b = prepared_by_app_id[_selected_app_key(request.app_b)]

        self.db.commit()
        messages.append(
            "[DB] Commit de registro completado antes de MobSF "
            f"app_a={prepared_a.app_version.id_app}:{prepared_a.app_version.version} "
            f"app_b={prepared_b.app_version.id_app}:{prepared_b.app_version.version}."
        )
        logger.info(
            "[DB] Commit de registro completado antes de MobSF app_a=%s:%s app_b=%s:%s",
            prepared_a.app_version.id_app,
            prepared_a.app_version.version,
            prepared_b.app_version.id_app,
            prepared_b.app_version.version,
        )

        analysis_results = self.app_analysis_service.ensure_mobsf_reports(
            [prepared_a, prepared_b]
        )

        report_a, messages_a = analysis_results[0]
        report_b, messages_b = analysis_results[1]

        messages.extend(messages_a)
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
