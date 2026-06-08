import logging
import os
from collections import OrderedDict
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import (
    AppAnalysisError,
    AppAnalysisService,
)
from app.application.services.app_registration_service import (
    AppRegistrationError,
    AppRegistrationService,
)
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
    RegisteredAppVersionItem,
    RegisterLocalApkRequest,
    RegisterLocalApkResponse,
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
        raise HTTPException(status_code=502, detail=str(exc))

    except Exception as exc:
        logger.exception("Error inesperado buscando aplicaciones")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado buscando aplicaciones: {exc}",
        )


@router.post("/register-local-apk", response_model=RegisterLocalApkResponse)
def register_local_apk(
    request: RegisterLocalApkRequest,
    db: Session = Depends(get_db_session),
):
    logger.info(
        "[MANUAL_APK] Solicitud de registro local recibida: apk_path=%s run_mobsf=%s source=%s",
        request.apk_path,
        request.run_mobsf,
        request.source_label,
    )

    registration_service = AppRegistrationService(db)
    try:
        prepared = registration_service.register_local_apk(
            apk_path=request.apk_path,
            title=request.title,
            developer=request.developer,
            category=request.category,
            icon=request.icon,
            source_label=request.source_label,
            version_date=request.version_date,
        )
        db.commit()
        logger.info(
            "[DB] Commit de registro completado antes de MobSF app_id=%s version=%s",
            prepared.app_version.id_app,
            prepared.app_version.version,
        )
        messages, mobsf_report_available = _maybe_run_mobsf(
            prepared=prepared,
            run_mobsf=request.run_mobsf,
            db=db,
        )
        return _local_apk_response(
            prepared=prepared,
            run_mobsf=request.run_mobsf,
            mobsf_report_available=mobsf_report_available,
            messages=messages,
        )

    except (AppRegistrationError, AppAnalysisError) as exc:
        db.rollback()
        logger.exception("Error controlado registrando APK local")
        raise HTTPException(status_code=422, detail=str(exc))

    except Exception as exc:
        db.rollback()
        logger.exception("Error inesperado registrando APK local")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado registrando APK local: {exc}",
        )


@router.post("/upload-apk", response_model=RegisterLocalApkResponse)
def upload_apk(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    developer: str | None = Form(default=None),
    category: str | None = Form(default=None),
    icon: str | None = Form(default=None),
    source_label: str | None = Form(default="mobile_upload"),
    run_mobsf: bool = Form(default=False),
    version_date: str | None = Form(default=None),
    db: Session = Depends(get_db_session),
):
    logger.info(
        "[UPLOAD] Solicitud multipart recibida filename=%s run_mobsf=%s source=%s",
        file.filename,
        run_mobsf,
        source_label,
    )

    registration_service = AppRegistrationService(db)
    staging_path: Path | None = None

    try:
        staging_path = _save_upload_to_staging(file)
        prepared = registration_service.register_uploaded_apk(
            apk_path=staging_path,
            title=title,
            developer=developer,
            category=category,
            icon=icon,
            source_label=source_label,
            version_date=version_date,
        )
        db.commit()
        logger.info(
            "[DB] Commit de registro completado antes de MobSF app_id=%s version=%s",
            prepared.app_version.id_app,
            prepared.app_version.version,
        )
        messages, mobsf_report_available = _maybe_run_mobsf(
            prepared=prepared,
            run_mobsf=run_mobsf,
            db=db,
        )
        return _local_apk_response(
            prepared=prepared,
            run_mobsf=run_mobsf,
            mobsf_report_available=mobsf_report_available,
            messages=messages,
        )

    except (AppRegistrationError, AppAnalysisError) as exc:
        db.rollback()
        _cleanup_staging_file(staging_path)
        logger.exception("Error controlado subiendo APK")
        raise HTTPException(status_code=422, detail=str(exc))

    except Exception as exc:
        db.rollback()
        _cleanup_staging_file(staging_path)
        logger.exception("Error inesperado subiendo APK")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado subiendo APK: {exc}",
        )


@router.get("/registered", response_model=RegisteredAppsResponse)
def get_registered_apps(db: Session = Depends(get_db_session)):
    rows = _get_all_registered_versions(db)
    grouped: OrderedDict[str, RegisteredAppItem] = OrderedDict()

    for app, version in rows:
        version_item = _model_to_registered_item(version)

        if app.id_app not in grouped:
            grouped[app.id_app] = RegisteredAppItem(
                app_id=app.id_app,
                name=app.nombre,
                developer=app.desarrollador,
                icon=app.icono,
                category=app.categoria or version.categoria or "",
                versions=[],
                version=version_item.version,
                version_code=version_item.version_code,
                version_date=version_item.version_date,
                integration_model=version_item.integration_model,
                integration_model_short=version_item.integration_model_short,
                mobsf_status=version_item.mobsf_status,
                mobsf_report_available=version_item.mobsf_report_available,
                apk_sha256=version_item.apk_sha256,
                ruta_apk=version_item.ruta_apk,
            )

        grouped[app.id_app].versions.append(version_item)

    results = list(grouped.values())
    return RegisteredAppsResponse(count=len(results), results=results)


@router.get("/analyzed", response_model=AnalyzedAppsResponse)
def get_analyzed_apps(db: Session = Depends(get_db_session)):
    rows = _get_latest_registered_versions(db)
    analyzed_rows = [
        (app, version) for app, version in rows if _has_mobsf_report(version)
    ]

    results = [
        AnalyzedAppItem(
            app_id=app.id_app,
            name=app.nombre,
            developer=app.desarrollador,
            icon=app.icono,
            version=version.version,
            category=app.categoria or version.categoria or "",
            analysis_date=(
                version.fecha_version.isoformat() if version.fecha_version else ""
            ),
            integration_model=_integration_model_to_api(version.modelo_integracion),
            mobsf_status=_mobsf_status_to_api(version.estado_mobsf),
            mobsf_report_available=True,
        )
        for app, version in analyzed_rows
    ]

    return AnalyzedAppsResponse(count=len(results), results=results)


def _maybe_run_mobsf(
    prepared,
    run_mobsf: bool,
    db: Session,
) -> tuple[list[str], bool]:
    messages = list(prepared.messages)
    mobsf_report_available = _has_mobsf_report_domain(prepared.app_version)

    if run_mobsf:
        logger.info(
            "[MOBSF] Registro/subida solicita análisis para app_id=%s version=%s",
            prepared.app_version.id_app,
            prepared.app_version.version,
        )
        analysis_service = AppAnalysisService(db)
        report, analysis_messages = analysis_service.ensure_mobsf_reports([prepared])[0]
        messages.extend(analysis_messages)
        prepared.app_version = report.version_app
        mobsf_report_available = report.mobsf_report is not None
    else:
        messages.append("[MOBSF] No se lanza MobSF porque run_mobsf=false.")

    return messages, mobsf_report_available


def _local_apk_response(
    prepared,
    run_mobsf: bool,
    mobsf_report_available: bool,
    messages: list[str],
) -> RegisterLocalApkResponse:
    version_item = _version_to_registered_item(prepared.app_version)
    app_item = RegisteredAppItem(
        app_id=prepared.application.id_app,
        name=prepared.application.nombre,
        developer=prepared.application.desarrollador,
        icon=prepared.application.icono,
        category=prepared.application.categoria or prepared.app_version.categoria or "",
        versions=[version_item],
        version=version_item.version,
        version_code=version_item.version_code,
        version_date=version_item.version_date,
        integration_model=version_item.integration_model,
        integration_model_short=version_item.integration_model_short,
        mobsf_status=version_item.mobsf_status,
        mobsf_report_available=version_item.mobsf_report_available,
        apk_sha256=version_item.apk_sha256,
        ruta_apk=version_item.ruta_apk,
    )

    return RegisterLocalApkResponse(
        app=app_item,
        version=version_item,
        run_mobsf=run_mobsf,
        mobsf_report_available=mobsf_report_available,
        already_registered=prepared.version_already_registered,
        messages=messages,
    )


def _save_upload_to_staging(file: UploadFile) -> Path:
    filename = Path(file.filename or "uploaded.apk").name
    suffix = Path(filename).suffix.lower()
    allowed_extensions = {".apk", ".xapk", ".apks", ".apkm"}

    if suffix not in allowed_extensions:
        raise AppRegistrationError(
            "Extensión no soportada para subida: "
            f"{suffix}. Extensiones válidas: {', '.join(sorted(allowed_extensions))}."
        )

    staging_dir = Path(
        os.getenv("APK_UPLOAD_STAGING_DIR", "/app/artifacts/tmp/uploads")
    )
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f"{uuid4().hex}_{filename}"

    max_upload_size_mb = int(
        os.getenv("MAX_UPLOAD_APK_SIZE_MB", os.getenv("MAX_APK_SIZE_MB", "300"))
    )
    max_bytes = max_upload_size_mb * 1024 * 1024
    written = 0

    with staging_path.open("wb") as output:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                output.close()
                _cleanup_staging_file(staging_path)
                raise AppRegistrationError(
                    f"El archivo subido supera el límite de {max_upload_size_mb} MB."
                )
            output.write(chunk)

    logger.info(
        "[UPLOAD] Archivo guardado en staging: %s (%.2f MB)",
        staging_path,
        written / (1024 * 1024),
    )
    return staging_path


def _cleanup_staging_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
            logger.info("[UPLOAD] Staging eliminado: %s", path)
    except OSError as exc:
        logger.warning("[UPLOAD] No se pudo eliminar staging %s: %s", path, exc)


def _get_all_registered_versions(
    db: Session,
) -> list[tuple[ApplicationModel, AppVersionModel]]:
    stmt = (
        select(ApplicationModel, AppVersionModel)
        .join(AppVersionModel, AppVersionModel.id_app == ApplicationModel.id_app)
        .order_by(
            ApplicationModel.nombre.asc(),
            AppVersionModel.fecha_version.desc().nullslast(),
            AppVersionModel.version_code.desc().nullslast(),
            AppVersionModel.version.desc(),
        )
    )
    return db.execute(stmt).all()


def _get_latest_registered_versions(
    db: Session,
) -> list[tuple[ApplicationModel, AppVersionModel]]:
    rows = _get_all_registered_versions(db)
    latest_by_app_id: OrderedDict[str, tuple[ApplicationModel, AppVersionModel]] = (
        OrderedDict()
    )

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


def _has_mobsf_report_domain(version) -> bool:
    return bool(
        version.estado_mobsf == MobSFAnalysisStatus.SUCCESS
        and version.hash_mobsf
        and version.ruta_informe_mobsf
    )


def _model_to_registered_item(version: AppVersionModel) -> RegisteredAppVersionItem:
    integration_model = _integration_model_to_api(version.modelo_integracion)
    return RegisteredAppVersionItem(
        version=version.version,
        version_code=version.version_code,
        version_date=(
            version.fecha_version.isoformat() if version.fecha_version else None
        ),
        integration_model=integration_model,
        integration_model_short=_integration_model_short(integration_model),
        mobsf_status=_mobsf_status_to_api(version.estado_mobsf),
        mobsf_report_available=_has_mobsf_report(version),
        apk_sha256=version.apk_sha256,
        ruta_apk=version.ruta_apk,
    )


def _version_to_registered_item(version) -> RegisteredAppVersionItem:
    integration_model = _integration_model_to_api(version.modelo_integracion.value)
    return RegisteredAppVersionItem(
        version=version.version,
        version_code=version.version_code,
        version_date=(
            version.fecha_version.isoformat() if version.fecha_version else None
        ),
        integration_model=integration_model,
        integration_model_short=_integration_model_short(integration_model),
        mobsf_status=_mobsf_status_to_api(version.estado_mobsf.value),
        mobsf_report_available=_has_mobsf_report_domain(version),
        apk_sha256=version.apk_sha256,
        ruta_apk=version.ruta_apk,
    )


def _integration_model_to_api(value: str) -> str:
    normalized = (value or "UNKNOWN").upper()

    if normalized == "HEALTH_CONNECT":
        return "health_connect"
    if normalized == "LEGACY":
        return "legacy"
    return "unknown"


def _integration_model_short(value: str) -> str:
    if value == "health_connect":
        return "HC"
    if value == "legacy":
        return "L"
    return "?"


def _mobsf_status_to_api(value: str) -> str:
    normalized = (value or "NOT_ANALYZED").upper()
    mapping = {
        "NOT_ANALYZED": "not_analyzed",
        "PENDING": "pending",
        "SUCCESS": "success",
        "ERROR": "error",
    }
    return mapping.get(normalized, "not_analyzed")
