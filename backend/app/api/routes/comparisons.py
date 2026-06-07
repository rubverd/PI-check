import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import AppAnalysisError
from app.application.services.app_registration_service import AppRegistrationError
from app.application.services.comparison_service import (
    ComparisonExecutionResult,
    ComparisonService,
)
from app.domain.entities.version_report import VersionReport
from app.infrastructure.database.session import get_db_session
from app.schemas.comparisons import (
    ComparisonAnalysisResponse,
    ComparisonRequest,
    MobSFReportInfo,
    VersionAppInfo,
    VersionReportInfo,
)

logger = logging.getLogger("pi-check")

router = APIRouter(
    prefix="/api/comparisons",
    tags=["comparisons"],
)


@router.post("/request", response_model=ComparisonAnalysisResponse)
def request_comparison(
    request: ComparisonRequest,
    db: Session = Depends(get_db_session),
):
    comparison_service = ComparisonService(db)

    try:
        result = comparison_service.create_comparison(request)
        db.commit()

        return _to_response(result)

    except (AppRegistrationError, AppAnalysisError) as exc:
        db.rollback()

        logger.exception("Error controlado creando comparativa")

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )

    except Exception as exc:
        db.rollback()

        logger.exception("Error inesperado creando comparativa")

        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado creando comparativa: {exc}",
        )


def _to_response(
    result: ComparisonExecutionResult,
) -> ComparisonAnalysisResponse:
    return ComparisonAnalysisResponse(
        comparison_id=result.comparison_id,
        status=result.status,
        message=result.message,
        messages=result.messages,
        app_a=_version_report_to_response(result.comparison.app_a),
        app_b=_version_report_to_response(result.comparison.app_b),
        id_indice_aplicado=result.comparison.id_indice_aplicado,
    )


def _version_report_to_response(
    version_report: VersionReport,
) -> VersionReportInfo:
    version_app = version_report.version_app
    mobsf_report = version_report.mobsf_report

    return VersionReportInfo(
        version_app=VersionAppInfo(
            id_app=version_app.id_app,
            version=version_app.version,
            version_code=version_app.version_code,
            fecha_version=(
                version_app.fecha_version.isoformat()
                if version_app.fecha_version
                else None
            ),
            categoria=version_app.categoria,
            modelo_integracion=version_app.modelo_integracion.value,
            apk_sha256=version_app.apk_sha256,
            estado_mobsf=version_app.estado_mobsf.value,
            hash_mobsf=version_app.hash_mobsf,
            ruta_informe_mobsf=version_app.ruta_informe_mobsf,
            ruta_apk=version_app.ruta_apk,
        ),
        mobsf_report=MobSFReportInfo(
            available=mobsf_report is not None,
            hash_mobsf=mobsf_report.hash_mobsf if mobsf_report else None,
            ruta_informe=mobsf_report.ruta_informe if mobsf_report else None,
            file_name=mobsf_report.file_name if mobsf_report else None,
            scan_type=mobsf_report.scan_type if mobsf_report else None,
            json_report=mobsf_report.json_report if mobsf_report else None,
        ),
    )
