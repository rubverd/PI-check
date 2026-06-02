import logging
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus
from app.infrastructure.database.session import get_db_session
from app.infrastructure.external.google_play_client import (
    GooglePlaySearchError,
    search_google_play_apps,
)
from app.infrastructure.persistence.models.application_model import ApplicationModel
from app.infrastructure.persistence.models.app_version_model import AppVersionModel
from app.schemas.apps import (
    AnalyzedAppItem,
    AnalyzedAppsResponse,
    AppSearchResponse,
    RegisteredAppItem,
    RegisteredAppsResponse,
)


logger = logging.getLogger("pi-check")

router = APIRouter(
    prefix="/api/apps",
    tags=["apps"],
)


@router.get("/search", response_model=AppSearchResponse)
def search_apps(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=20),
    lang: str = "es",
    country: str = "es",
):
    try:
        results = search_google_play_apps(
            query=q,
            limit=limit,
            lang=lang,
            country=country,
        )

        return AppSearchResponse(
            query=q,
            count=len(results),
            results=results,
        )

    except GooglePlaySearchError as exc:
        logger.exception("Error controlado buscando aplicaciones")

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception("Error inesperado buscando aplicaciones")

        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado buscando aplicaciones: {exc}",
        )


@router.get("/registered", response_model=RegisteredAppsResponse)
def get_registered_apps(db: Session = Depends(get_db_session)):
    rows = _get_latest_registered_versions(db)

    results = [
        RegisteredAppItem(
            app_id=app.id_app,
            name=app.nombre,
            developer=app.desarrollador,
            icon=app.icono,
            category=app.categoria or version.categoria or "",
            version=version.version,
            version_code=version.version_code,
            version_date=version.fecha_version.isoformat()
            if version.fecha_version
            else None,
            integration_model=_integration_model_to_api(version.modelo_integracion),
            mobsf_status=_mobsf_status_to_api(version.estado_mobsf),
            mobsf_report_available=_has_mobsf_report(version),
        )
        for app, version in rows
    ]

    return RegisteredAppsResponse(
        count=len(results),
        results=results,
    )


@router.get("/analyzed", response_model=AnalyzedAppsResponse)
def get_analyzed_apps(db: Session = Depends(get_db_session)):
    rows = _get_latest_registered_versions(db)

    analyzed_rows = [
        (app, version)
        for app, version in rows
        if _has_mobsf_report(version)
    ]

    results = [
        AnalyzedAppItem(
            app_id=app.id_app,
            name=app.nombre,
            developer=app.desarrollador,
            icon=app.icono,
            version=version.version,
            category=app.categoria or version.categoria or "",
            analysis_date=version.fecha_version.isoformat()
            if version.fecha_version
            else "",
            integration_model=_integration_model_to_api(version.modelo_integracion),
            mobsf_status=_mobsf_status_to_api(version.estado_mobsf),
            mobsf_report_available=True,
        )
        for app, version in analyzed_rows
    ]

    return AnalyzedAppsResponse(
        count=len(results),
        results=results,
    )


def _get_latest_registered_versions(
    db: Session,
) -> list[tuple[ApplicationModel, AppVersionModel]]:
    stmt = (
        select(ApplicationModel, AppVersionModel)
        .join(
            AppVersionModel,
            AppVersionModel.id_app == ApplicationModel.id_app,
        )
        .order_by(
            ApplicationModel.nombre.asc(),
            AppVersionModel.fecha_version.desc().nullslast(),
            AppVersionModel.version_code.desc().nullslast(),
            AppVersionModel.version.desc(),
        )
    )

    rows = db.execute(stmt).all()

    latest_by_app_id: OrderedDict[
        str,
        tuple[ApplicationModel, AppVersionModel],
    ] = OrderedDict()

    for app, version in rows:
        if app.id_app not in latest_by_app_id:
            latest_by_app_id[app.id_app] = (app, version)

    return list(latest_by_app_id.values())


def _has_mobsf_report(version: AppVersionModel) -> bool:
    return bool(
        version.estado_mobsf == MobSFAnalysisStatus.SUCCESS.value
        and version.hash_mobsf
        and version.ruta_informe_mobsf
    )


def _integration_model_to_api(value: str) -> str:
    normalized = (value or "UNKNOWN").upper()

    if normalized == "HEALTH_CONNECT":
        return "health_connect"

    if normalized == "LEGACY":
        return "legacy"

    return "unknown"


def _mobsf_status_to_api(value: str) -> str:
    normalized = (value or "NOT_ANALYZED").upper()

    mapping = {
        "NOT_ANALYZED": "not_analyzed",
        "PENDING": "pending",
        "SUCCESS": "success",
        "ERROR": "error",
    }

    return mapping.get(normalized, "not_analyzed")