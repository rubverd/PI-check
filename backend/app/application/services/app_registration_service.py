import logging
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.entities.application import Application
from app.domain.entities.app_version import AppVersion
from app.domain.value_objects.integration_model import IntegrationModel
from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus
from app.infrastructure.external.apkeep_client import (
    download_apks_with_apkeep_in_parallel,
)
from app.infrastructure.external.apk_metadata_extractor import (
    ExtractedApkMetadata,
    extract_apk_metadata,
    is_valid_version_string,
    parse_date_or_none,
)
from app.infrastructure.persistence.repositories.application_repository import (
    ApplicationRepository,
)
from app.infrastructure.persistence.repositories.app_version_repository import (
    AppVersionRepository,
)
from app.schemas.comparisons import SelectedAppMetadata

logger = logging.getLogger("pi-check")

SUPPORTED_LOCAL_APK_EXTENSIONS = {".apk", ".xapk", ".apks", ".apkm"}


class AppRegistrationError(Exception):
    """Error controlado durante el registro/preparación de una aplicación."""


@dataclass
class PreparedAppVersion:
    selected_app: SelectedAppMetadata
    application: Application
    app_version: AppVersion
    apk_path: Path | None
    app_already_registered: bool
    version_already_registered: bool
    messages: list[str]


class AppRegistrationService:
    def __init__(self, db: Session):
        self.db = db
        self.application_repository = ApplicationRepository(db)
        self.app_version_repository = AppVersionRepository(db)

    def prepare_apps_for_comparison(
        self,
        selected_apps: list[SelectedAppMetadata],
        comparison_id: str,
        download_apks: bool = True,
    ) -> tuple[dict[str, PreparedAppVersion], list[str]]:
        messages: list[str] = []

        unique_apps = list(
            {_selected_app_key(app): app for app in selected_apps}.values()
        )

        logger.info(
            "[REGISTRATION] Preparando %s aplicaciones para comparison_id=%s",
            len(unique_apps),
            comparison_id,
        )

        messages.append(
            f"Se inicia preparación/registro de {len(unique_apps)} aplicaciones."
        )

        downloaded_files_by_app_id: dict[str, Path] = {}

        if download_apks:
            downloaded_files_by_app_id, download_messages = (
                self._download_selected_apps_in_parallel(
                    selected_apps=unique_apps,
                    comparison_id=comparison_id,
                )
            )
            messages.extend(download_messages)
        else:
            messages.append(
                "La descarga de APKs está desactivada. "
                "Solo se podrán registrar versiones si Google Play devuelve una versión válida."
            )

        prepared_by_app_id: dict[str, PreparedAppVersion] = {}

        for selected_app in unique_apps:
            apk_path = downloaded_files_by_app_id.get(selected_app.app_id)

            prepared = self.prepare_single_app(
                selected_app=selected_app,
                apk_path=apk_path,
            )

            prepared_by_app_id[_selected_app_key(selected_app)] = prepared
            messages.extend(prepared.messages)

        messages.append("Preparación/registro de aplicaciones finalizada.")

        return prepared_by_app_id, messages

    def prepare_single_app(
        self,
        selected_app: SelectedAppMetadata,
        apk_path: Path | None,
    ) -> PreparedAppVersion:
        messages: list[str] = []

        logger.info(
            "[REGISTRATION] Preparando aplicación app_id=%s, title=%s",
            selected_app.app_id,
            selected_app.title,
        )

        messages.append(f"[REGISTRATION] Preparando aplicación {selected_app.app_id}.")

        existing_application = self.application_repository.find_by_id(
            selected_app.app_id
        )
        app_already_registered = existing_application is not None

        messages.append(
            "[REGISTRATION] Aplicación registrada previamente: "
            f"{'sí' if app_already_registered else 'no'}."
        )

        logger.info(
            "[REGISTRATION] Aplicación %s registrada previamente: %s",
            selected_app.app_id,
            app_already_registered,
        )

        if apk_path is not None:
            if not apk_path.exists():
                raise AppRegistrationError(
                    f"El archivo descargado para {selected_app.title} no existe: "
                    f"{apk_path}"
                )

            logger.info(
                "[METADATA] Extrayendo metadatos desde APK para app_id=%s: %s",
                selected_app.app_id,
                apk_path,
            )

            messages.append(
                f"[METADATA] Extrayendo metadatos desde archivo: {apk_path}."
            )

            extracted_metadata = extract_apk_metadata(
                apk_path=apk_path,
                fallback_app_id=selected_app.app_id,
                fallback_version=selected_app.version,
                fallback_category=selected_app.genre,
                fallback_version_date=selected_app.version_date,
            )

        else:
            existing_version = self._find_selected_existing_version(selected_app)

            if existing_version is not None and existing_application is not None:
                saved_application = existing_application
                saved_version = existing_version
                existing_apk_path = (
                    Path(existing_version.ruta_apk)
                    if existing_version.ruta_apk
                    else None
                )

                messages.append(
                    f"[DB] Se reutiliza versión registrada: {existing_version.id_app} "
                    f"versión {existing_version.version}."
                )

                return PreparedAppVersion(
                    selected_app=selected_app,
                    application=saved_application,
                    app_version=saved_version,
                    apk_path=existing_apk_path,
                    app_already_registered=app_already_registered,
                    version_already_registered=True,
                    messages=messages,
                )

            extracted_metadata = self._build_metadata_without_apk(
                selected_app=selected_app,
                existing_application=existing_application,
            )

        messages.append(
            "[METADATA] Metadatos detectados: "
            f"id_app={extracted_metadata.id_app}, "
            f"version={extracted_metadata.version}, "
            f"version_code={extracted_metadata.version_code}, "
            f"modelo_integracion={extracted_metadata.modelo_integracion.value}."
        )

        logger.info(
            "[METADATA] app_id=%s version=%s version_code=%s integration=%s sha256=%s",
            extracted_metadata.id_app,
            extracted_metadata.version,
            extracted_metadata.version_code,
            extracted_metadata.modelo_integracion.value,
            extracted_metadata.apk_sha256,
        )

        logger.info(
            "[INTEGRATION] Modelo detectado para app_id=%s: %s",
            extracted_metadata.id_app,
            extracted_metadata.modelo_integracion.value,
        )

        application = Application(
            id_app=extracted_metadata.id_app,
            nombre=selected_app.title or extracted_metadata.id_app,
            icono=selected_app.icon,
            categoria=selected_app.genre or extracted_metadata.categoria,
            desarrollador=selected_app.developer,
            modelo_integracion_actual=extracted_metadata.modelo_integracion,
        )

        saved_application = self.application_repository.save(application)

        messages.append(
            f"[DB] Aplicación registrada/actualizada: {saved_application.id_app}."
        )

        existing_version = self.app_version_repository.find_by_id(
            id_app=extracted_metadata.id_app,
            version=extracted_metadata.version,
        )

        version_already_registered = existing_version is not None

        messages.append(
            "[VERSION] Versión registrada previamente: "
            f"{'sí' if version_already_registered else 'no'}."
        )

        if existing_version is None:
            app_version = AppVersion(
                id_app=extracted_metadata.id_app,
                version=extracted_metadata.version,
                fecha_version=extracted_metadata.fecha_version,
                categoria=extracted_metadata.categoria,
                modelo_integracion=extracted_metadata.modelo_integracion,
                version_code=extracted_metadata.version_code,
                apk_sha256=extracted_metadata.apk_sha256,
                ruta_apk=str(apk_path) if apk_path else None,
                estado_mobsf=MobSFAnalysisStatus.NOT_ANALYZED,
            )

            saved_version = self.app_version_repository.save(app_version)

            messages.append(
                f"[DB] Nueva versión registrada: {saved_version.id_app} "
                f"versión {saved_version.version}."
            )

        else:
            existing_version.version_code = extracted_metadata.version_code
            existing_version.fecha_version = extracted_metadata.fecha_version
            existing_version.categoria = extracted_metadata.categoria
            existing_version.modelo_integracion = extracted_metadata.modelo_integracion

            if extracted_metadata.apk_sha256:
                existing_version.apk_sha256 = extracted_metadata.apk_sha256

            if apk_path is not None:
                existing_version.ruta_apk = str(apk_path)

            saved_version = self.app_version_repository.save(existing_version)

            messages.append(
                f"[DB] Versión existente actualizada: {saved_version.id_app} "
                f"versión {saved_version.version}."
            )

        return PreparedAppVersion(
            selected_app=selected_app,
            application=saved_application,
            app_version=saved_version,
            apk_path=apk_path,
            app_already_registered=app_already_registered,
            version_already_registered=version_already_registered,
            messages=messages,
        )

    def register_local_apk(
        self,
        apk_path: str,
        title: str | None = None,
        developer: str | None = None,
        category: str | None = None,
        icon: str | None = None,
        source_label: str | None = None,
    ) -> PreparedAppVersion:
        path = Path(apk_path)
        messages: list[str] = []

        logger.info(
            "[MANUAL_APK] Solicitud de registro local recibida: path=%s source=%s",
            path,
            source_label,
        )
        messages.append(f"[MANUAL_APK] Solicitud de registro local recibida: {path}.")

        if not path.exists() or not path.is_file():
            raise AppRegistrationError(
                f"El archivo APK/XAPK/APKS/APKM no existe: {path}"
            )

        if path.suffix.lower() not in SUPPORTED_LOCAL_APK_EXTENSIONS:
            raise AppRegistrationError(
                "Extensión no soportada para registro local: "
                f"{path.suffix}. Extensiones válidas: "
                f"{', '.join(sorted(SUPPORTED_LOCAL_APK_EXTENSIONS))}."
            )

        selected_app = SelectedAppMetadata(
            app_id=f"manual.{path.stem}",
            title=title or path.stem,
            developer=developer,
            icon=icon,
            genre=category,
            version=None,
            version_date=None,
        )

        prepared = self.prepare_single_app(selected_app=selected_app, apk_path=path)
        prepared.messages = messages + prepared.messages
        return prepared

    def _find_selected_existing_version(
        self,
        selected_app: SelectedAppMetadata,
    ) -> AppVersion | None:
        selected_version = selected_app.selected_version or selected_app.version

        if selected_version:
            existing = self.app_version_repository.find_by_id(
                id_app=selected_app.app_id,
                version=selected_version,
            )
            if existing is not None:
                return existing

        if selected_app.apk_sha256:
            return self.app_version_repository.find_by_apk_sha256(
                id_app=selected_app.app_id,
                apk_sha256=selected_app.apk_sha256,
            )

        return None

    def _download_selected_apps_in_parallel(
        self,
        selected_apps: list[SelectedAppMetadata],
        comparison_id: str,
    ) -> tuple[dict[str, Path], list[str]]:
        messages: list[str] = []

        apk_tmp_dir = os.getenv(
            "APK_TMP_DIR",
            os.getenv("APK_OUTPUT_DIR", "/app/artifacts/tmp/apks"),
        )

        app_downloads = []
        apps_to_download: list[SelectedAppMetadata] = []

        for selected_app in selected_apps:
            if self._find_selected_existing_version(selected_app) is not None:
                messages.append(
                    f"[APK] Se reutilizará versión registrada de {selected_app.title}; "
                    "no se descarga de Google Play."
                )
                continue

            app_downloads.append(
                (
                    selected_app.app_id,
                    Path(apk_tmp_dir) / comparison_id / selected_app.app_id,
                )
            )
            apps_to_download.append(selected_app)

        messages.append(f"[APK] Se descargarán {len(app_downloads)} APKs en paralelo.")

        logger.info(
            "[APK] Iniciando descarga paralela de %s APKs para comparison_id=%s",
            len(app_downloads),
            comparison_id,
        )

        if not app_downloads:
            messages.append("[APK] No hay APKs que descargar.")
            return {}, messages

        download_results = download_apks_with_apkeep_in_parallel(
            app_downloads=app_downloads,
            source="apk-pure",
            timeout_seconds=300,
        )

        selected_apps_by_id = {app.app_id: app for app in apps_to_download}
        apk_paths_by_app_id: dict[str, Path] = {}

        for download_info in download_results:
            selected_app = selected_apps_by_id.get(download_info.app_id)
            app_title = selected_app.title if selected_app else download_info.app_id

            if not download_info.success:
                raise AppRegistrationError(
                    f"No se pudo descargar el APK de {app_title}: "
                    f"{download_info.error}"
                )

            apk_path = self._select_analysis_file(download_info.apk_files)

            if apk_path is None:
                raise AppRegistrationError(
                    f"La descarga de {app_title} finalizó, "
                    "pero no se encontró ningún APK/XAPK/APKS/APKM."
                )

            apk_paths_by_app_id[download_info.app_id] = apk_path

            size_mb = apk_path.stat().st_size / (1024 * 1024)

            messages.append(
                f"[APK] Archivo preparado para {app_title}: "
                f"{apk_path} ({size_mb:.2f} MB)."
            )

            logger.info(
                "[APK] Archivo seleccionado para app_id=%s: %s (%.2f MB)",
                download_info.app_id,
                apk_path,
                size_mb,
            )

        messages.append("[APK] Descarga paralela finalizada.")

        return apk_paths_by_app_id, messages

    def _build_metadata_without_apk(
        self,
        selected_app: SelectedAppMetadata,
        existing_application: Application | None,
    ) -> ExtractedApkMetadata:
        if not is_valid_version_string(selected_app.version):
            raise AppRegistrationError(
                f"No se puede registrar {selected_app.title} sin analizar el APK, "
                f"porque la versión recibida no es concreta: {selected_app.version!r}."
            )

        if existing_application is not None:
            integration_model = existing_application.modelo_integracion_actual
        else:
            integration_model = IntegrationModel.UNKNOWN

        logger.info(
            "[METADATA] Se registrará %s usando versión recibida de Google Play: %s",
            selected_app.app_id,
            selected_app.version,
        )

        return ExtractedApkMetadata(
            id_app=selected_app.app_id,
            version=selected_app.version.strip()[:100],
            version_code=None,
            fecha_version=parse_date_or_none(selected_app.version_date),
            categoria=selected_app.genre,
            modelo_integracion=integration_model,
            apk_sha256=None,
        )

    def _select_analysis_file(self, apk_files: list[str]) -> Path | None:
        if not apk_files:
            return None

        priority = {
            ".apk": 0,
            ".xapk": 1,
            ".apks": 2,
            ".apkm": 3,
        }

        sorted_files = sorted(
            [Path(path) for path in apk_files],
            key=lambda path: priority.get(path.suffix.lower(), 99),
        )

        return sorted_files[0]


def _selected_app_key(selected_app: SelectedAppMetadata) -> str:
    return "|".join(
        [
            selected_app.app_id,
            selected_app.selected_version or selected_app.version or "",
            selected_app.apk_sha256 or "",
        ]
    )
