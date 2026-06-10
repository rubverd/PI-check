import logging
import os
import re
import shutil
from contextlib import suppress
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
            f"[REGISTRATION] Se inicia preparación/registro de {len(unique_apps)} aplicaciones."
        )

        downloaded_files_by_app_id: dict[str, Path] = {}

        if download_apks:
            downloaded_files_by_app_id, download_messages = (
                self._download_missing_selected_apps(
                    selected_apps=unique_apps,
                    comparison_id=comparison_id,
                )
            )
            messages.extend(download_messages)
        else:
            messages.append(
                "[APK] La descarga está desactivada. Solo se reutilizarán versiones "
                "registradas o versiones concretas devueltas por Google Play."
            )

        prepared_by_key: dict[str, PreparedAppVersion] = {}

        for selected_app in unique_apps:
            apk_path = downloaded_files_by_app_id.get(selected_app.app_id)
            prepared = self.prepare_single_app(
                selected_app=selected_app,
                apk_path=apk_path,
                cleanup_source_if_duplicate=apk_path is not None,
                move_source_to_storage=apk_path is not None,
            )
            prepared_by_key[_selected_app_key(selected_app)] = prepared
            messages.extend(prepared.messages)

        messages.append(
            "[REGISTRATION] Preparación/registro de aplicaciones finalizada."
        )

        return prepared_by_key, messages

    def prepare_single_app(
        self,
        selected_app: SelectedAppMetadata,
        apk_path: Path | None,
        cleanup_source_if_duplicate: bool = False,
        move_source_to_storage: bool = False,
    ) -> PreparedAppVersion:
        messages: list[str] = []

        logger.info(
            "[REGISTRATION] Preparando aplicación app_id=%s title=%s selected_version=%s version=%s",
            selected_app.app_id,
            selected_app.title,
            selected_app.selected_version,
            selected_app.version,
        )
        messages.append(f"[REGISTRATION] Preparando aplicación {selected_app.app_id}.")

        if apk_path is not None:
            return self.ingest_apk(
                apk_path=apk_path,
                title=selected_app.title,
                developer=selected_app.developer,
                category=selected_app.genre,
                icon=selected_app.icon,
                source_label="comparison_download",
                fallback_app_id=selected_app.app_id,
                fallback_version=selected_app.version,
                fallback_version_date=selected_app.version_date,
                cleanup_source_if_duplicate=cleanup_source_if_duplicate,
                move_source_to_storage=move_source_to_storage,
                initial_messages=messages,
            )

        existing_application = self.application_repository.find_by_id(
            selected_app.app_id
        )
        existing_version = self._find_selected_existing_version(selected_app)

        if existing_version is not None and existing_application is not None:
            logger.info(
                "[VERSION_CHECK] Versión ya registrada. Se evita descarga APK. app_id=%s version=%s",
                existing_version.id_app,
                existing_version.version,
            )
            messages.append(
                f"[VERSION_CHECK] Versión ya registrada para {existing_version.id_app} "
                f"versión {existing_version.version}. Se evita descarga APK."
            )

            existing_apk_path = (
                Path(existing_version.ruta_apk) if existing_version.ruta_apk else None
            )

            return PreparedAppVersion(
                selected_app=selected_app,
                application=existing_application,
                app_version=existing_version,
                apk_path=existing_apk_path,
                app_already_registered=True,
                version_already_registered=True,
                messages=messages,
            )

        extracted_metadata = self._build_metadata_without_apk(
            selected_app=selected_app,
            existing_application=existing_application,
        )

        return self._save_metadata_without_apk(
            selected_app=selected_app,
            extracted_metadata=extracted_metadata,
            existing_application=existing_application,
            initial_messages=messages,
        )

    def ingest_apk(
        self,
        apk_path: Path,
        title: str | None = None,
        developer: str | None = None,
        category: str | None = None,
        icon: str | None = None,
        source_label: str | None = None,
        fallback_app_id: str | None = None,
        fallback_version: str | None = None,
        fallback_version_date: str | None = None,
        cleanup_source_if_duplicate: bool = False,
        move_source_to_storage: bool = False,
        initial_messages: list[str] | None = None,
    ) -> PreparedAppVersion:
        messages = list(initial_messages or [])
        path = Path(apk_path)

        self._validate_apk_file(path)

        logger.info(
            "[APK] Ingestando APK source=%s path=%s cleanup_duplicate=%s move=%s",
            source_label,
            path,
            cleanup_source_if_duplicate,
            move_source_to_storage,
        )
        messages.append(f"[APK] Ingestando archivo APK/XAPK/APKS/APKM: {path}.")

        try:
            extracted_metadata = extract_apk_metadata(
                apk_path=path,
                fallback_app_id=fallback_app_id or f"manual.{path.stem}",
                fallback_version=fallback_version,
                fallback_category=category,
                fallback_version_date=fallback_version_date,
            )
        finally:
            self._cleanup_metadata_extraction_dir(path, messages)

        messages.append(
            "[METADATA] APK detectado como "
            f"app_id={extracted_metadata.id_app}, "
            f"version={extracted_metadata.version}, "
            f"version_code={extracted_metadata.version_code}, "
            f"modelo_integracion={extracted_metadata.modelo_integracion.value}."
        )
        logger.info(
            "[METADATA] APK detectado app_id=%s version=%s version_code=%s sha256=%s integration=%s",
            extracted_metadata.id_app,
            extracted_metadata.version,
            extracted_metadata.version_code,
            extracted_metadata.apk_sha256,
            extracted_metadata.modelo_integracion.value,
        )
        logger.info(
            "[INTEGRATION] Modelo detectado para app_id=%s: %s",
            extracted_metadata.id_app,
            extracted_metadata.modelo_integracion.value,
        )

        if extracted_metadata.app_label:
            messages.append(
                f"[METADATA] Nombre de aplicación extraído del APK: {extracted_metadata.app_label}."
            )
        else:
            messages.append(
                "[METADATA] No se pudo extraer nombre visible del APK; se usará fallback."
            )

        if extracted_metadata.icon:
            messages.append(f"[ICON] Icono extraído del APK: {extracted_metadata.icon}.")
        else:
            messages.append("[ICON] No se encontró icono PNG/WEBP extraíble en el APK.")

        existing_application = self.application_repository.find_by_id(
            extracted_metadata.id_app
        )
        app_already_registered = existing_application is not None

        existing_version = self.app_version_repository.find_by_id(
            id_app=extracted_metadata.id_app,
            version=extracted_metadata.version,
        )
        version_already_registered = existing_version is not None

        if existing_version is not None:
            messages.append(
                f"[DEDUP] Tras analizar APK, la versión ya existía: "
                f"{existing_version.id_app} {existing_version.version}. No se duplica."
            )
            logger.info(
                "[DEDUP] Versión existente tras extracción app_id=%s version=%s",
                existing_version.id_app,
                existing_version.version,
            )

            existing_apk_path = (
                Path(existing_version.ruta_apk) if existing_version.ruta_apk else None
            )
            has_valid_managed_apk = self._is_valid_managed_apk_path(existing_apk_path)

            if has_valid_managed_apk:
                messages.append(
                    "[DEDUP] Versión existente con APK gestionado. "
                    "Se elimina temporal y se reutiliza ruta_apk."
                )
                logger.info(
                    "[DEDUP] Versión existente con APK gestionado app_id=%s version=%s ruta_apk=%s",
                    existing_version.id_app,
                    existing_version.version,
                    existing_version.ruta_apk,
                )
                if cleanup_source_if_duplicate:
                    self._cleanup_source_file(path, messages)
            else:
                messages.append(
                    "[DEDUP] Versión existente sin APK gestionado válido. "
                    "Se conserva APK descargado/subido en almacenamiento gestionado."
                )
                logger.info(
                    "[DEDUP] Versión existente sin ruta_apk válida app_id=%s version=%s ruta_apk=%s",
                    existing_version.id_app,
                    existing_version.version,
                    existing_version.ruta_apk,
                )
                managed_apk_path = self._store_apk(
                    source_path=path,
                    metadata=extracted_metadata,
                    move_source=move_source_to_storage,
                    messages=messages,
                )
                existing_version.ruta_apk = str(managed_apk_path)
                messages.append(
                    f"[DB] ruta_apk actualizada para versión existente: {managed_apk_path}."
                )
                logger.info(
                    "[DB] ruta_apk actualizada app_id=%s version=%s ruta_apk=%s",
                    existing_version.id_app,
                    existing_version.version,
                    managed_apk_path,
                )

            if extracted_metadata.version_code is not None:
                existing_version.version_code = extracted_metadata.version_code
            existing_version.fecha_version = (
                extracted_metadata.fecha_version or existing_version.fecha_version
            )
            existing_version.categoria = (
                extracted_metadata.categoria or existing_version.categoria
            )
            existing_version.modelo_integracion = extracted_metadata.modelo_integracion
            existing_version.apk_sha256 = (
                extracted_metadata.apk_sha256 or existing_version.apk_sha256
            )
            saved_version = self.app_version_repository.save(existing_version)

            saved_application = self._save_application_metadata(
                id_app=saved_version.id_app,
                existing_application=existing_application,
                extracted_metadata=extracted_metadata,
                title=title,
                developer=developer,
                category=category or saved_version.categoria,
                explicit_icon=icon,
                messages=messages,
            )

            self._cleanup_download_parent_dirs(path, messages)

            return PreparedAppVersion(
                selected_app=_selected_metadata_from_saved(
                    saved_application,
                    title=title,
                    version=saved_version.version,
                    version_date=(
                        saved_version.fecha_version.isoformat()
                        if saved_version.fecha_version
                        else None
                    ),
                ),
                application=saved_application,
                app_version=saved_version,
                apk_path=(
                    Path(saved_version.ruta_apk) if saved_version.ruta_apk else None
                ),
                app_already_registered=app_already_registered,
                version_already_registered=True,
                messages=messages,
            )

        if existing_application is None:
            messages.append(
                f"[DB] Aplicación no existente. Se registra aplicación y versión: {extracted_metadata.id_app}."
            )
        else:
            messages.append(
                f"[DB] Aplicación existente. Se registra nueva versión: {extracted_metadata.id_app}."
            )

        saved_application = self._save_application_metadata(
            id_app=extracted_metadata.id_app,
            existing_application=existing_application,
            extracted_metadata=extracted_metadata,
            title=title,
            developer=developer,
            category=category or extracted_metadata.categoria,
            explicit_icon=icon,
            messages=messages,
        )

        managed_apk_path = self._store_apk(
            source_path=path,
            metadata=extracted_metadata,
            move_source=move_source_to_storage,
            messages=messages,
        )
        self._cleanup_download_parent_dirs(path, messages)

        app_version = AppVersion(
            id_app=extracted_metadata.id_app,
            version=extracted_metadata.version,
            fecha_version=extracted_metadata.fecha_version,
            categoria=extracted_metadata.categoria or category,
            modelo_integracion=extracted_metadata.modelo_integracion,
            version_code=extracted_metadata.version_code,
            apk_sha256=extracted_metadata.apk_sha256,
            ruta_apk=str(managed_apk_path),
            estado_mobsf=MobSFAnalysisStatus.NOT_ANALYZED,
        )
        saved_version = self.app_version_repository.save(app_version)

        messages.append(
            f"[DB] Nueva versión registrada: {saved_version.id_app} "
            f"versión {saved_version.version}."
        )
        messages.append(
            f"[APK] APK conservado en ubicación gestionada: {managed_apk_path}."
        )

        return PreparedAppVersion(
            selected_app=_selected_metadata_from_saved(
                saved_application,
                title=title,
                version=saved_version.version,
                version_date=(
                    saved_version.fecha_version.isoformat()
                    if saved_version.fecha_version
                    else None
                ),
            ),
            application=saved_application,
            app_version=saved_version,
            apk_path=managed_apk_path,
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
        version_date: str | None = None,
    ) -> PreparedAppVersion:
        path = self._validate_manual_apk_path(Path(apk_path))
        messages = [f"[MANUAL_APK] Solicitud de registro local recibida: {path}."]

        logger.info(
            "[MANUAL_APK] Solicitud de registro local recibida: path=%s source=%s",
            path,
            source_label,
        )

        return self.ingest_apk(
            apk_path=path,
            title=title,
            developer=developer,
            category=category,
            icon=icon,
            source_label=source_label or "manual_dataset",
            fallback_app_id=f"manual.{path.stem}",
            fallback_version_date=version_date,
            cleanup_source_if_duplicate=False,
            move_source_to_storage=False,
            initial_messages=messages,
        )

    def register_uploaded_apk(
        self,
        apk_path: Path,
        title: str | None = None,
        developer: str | None = None,
        category: str | None = None,
        icon: str | None = None,
        source_label: str | None = None,
        version_date: str | None = None,
    ) -> PreparedAppVersion:
        messages = [f"[UPLOAD] Solicitud de subida recibida: {apk_path}."]
        logger.info("[UPLOAD] Ingestando APK subido desde staging: %s", apk_path)

        return self.ingest_apk(
            apk_path=apk_path,
            title=title,
            developer=developer,
            category=category,
            icon=icon,
            source_label=source_label or "mobile_upload",
            fallback_app_id=f"upload.{apk_path.stem}",
            fallback_version_date=version_date,
            cleanup_source_if_duplicate=True,
            move_source_to_storage=True,
            initial_messages=messages,
        )

    def _save_application_metadata(
        self,
        id_app: str,
        existing_application: Application | None,
        extracted_metadata: ExtractedApkMetadata,
        title: str | None,
        developer: str | None,
        category: str | None,
        explicit_icon: str | None,
        messages: list[str],
    ) -> Application:
        resolved_name = self._resolve_application_name(
            extracted_label=extracted_metadata.app_label,
            explicit_title=title,
            existing_name=existing_application.nombre if existing_application else None,
            app_id=id_app,
        )
        resolved_icon = self._resolve_application_icon(
            explicit_icon=explicit_icon,
            extracted_icon=extracted_metadata.icon,
            existing_icon=existing_application.icono if existing_application else None,
        )

        if resolved_name == id_app and not extracted_metadata.app_label:
            messages.append(f"[METADATA] No se pudo extraer nombre visible; se usa fallback: {id_app}.")

        if existing_application is not None:
            if resolved_name != existing_application.nombre:
                messages.append(f"[DB] Nombre de aplicación actualizado: {existing_application.nombre} -> {resolved_name}.")
            if resolved_icon and resolved_icon != existing_application.icono:
                messages.append(f"[DB] Icono de aplicación actualizado: {resolved_icon}.")

        application = Application(
            id_app=id_app,
            nombre=resolved_name,
            icono=resolved_icon,
            categoria=category or (existing_application.categoria if existing_application else None),
            desarrollador=developer
            or (existing_application.desarrollador if existing_application else None),
            modelo_integracion_actual=extracted_metadata.modelo_integracion,
        )
        return self.application_repository.save(application)

    def _resolve_application_name(
        self,
        extracted_label: str | None,
        explicit_title: str | None,
        existing_name: str | None,
        app_id: str,
    ) -> str:
        for candidate in (extracted_label, explicit_title, existing_name):
            if candidate and not _is_bad_generated_name(candidate, app_id):
                return candidate.strip()
        return app_id

    def _resolve_application_icon(
        self,
        explicit_icon: str | None,
        extracted_icon: str | None,
        existing_icon: str | None,
    ) -> str | None:
        if explicit_icon:
            return explicit_icon
        if existing_icon:
            return existing_icon
        return extracted_icon

    def _find_selected_existing_version(
        self,
        selected_app: SelectedAppMetadata,
    ) -> AppVersion | None:
        selected_version = selected_app.selected_version or selected_app.version

        logger.info(
            "[VERSION_CHECK] Comprobando versión solicitada app_id=%s version=%s version_code=%s sha256=%s",
            selected_app.app_id,
            selected_version,
            selected_app.version_code,
            selected_app.apk_sha256,
        )

        if is_valid_version_string(selected_version):
            existing = self.app_version_repository.find_by_id(
                id_app=selected_app.app_id,
                version=selected_version.strip(),
            )
            if existing is not None:
                logger.info(
                    "[VERSION_CHECK] Versión ya registrada. Se evita descarga APK. app_id=%s version=%s",
                    selected_app.app_id,
                    selected_version,
                )
                return existing

        if selected_app.apk_sha256:
            existing = self.app_version_repository.find_by_apk_sha256(
                id_app=selected_app.app_id,
                apk_sha256=selected_app.apk_sha256,
            )
            if existing is not None:
                logger.info(
                    "[VERSION_CHECK] Versión encontrada por apk_sha256. app_id=%s version=%s",
                    selected_app.app_id,
                    existing.version,
                )
                return existing

        logger.info(
            "[VERSION_CHECK] Versión no registrada o no concreta. Se requiere APK. app_id=%s version=%s",
            selected_app.app_id,
            selected_version,
        )
        return None

    def _download_missing_selected_apps(
        self,
        selected_apps: list[SelectedAppMetadata],
        comparison_id: str,
    ) -> tuple[dict[str, Path], list[str]]:
        messages: list[str] = []
        apk_tmp_dir = os.getenv(
            "APK_TMP_DIR",
            os.getenv("APK_OUTPUT_DIR", "/app/artifacts/tmp/apks"),
        )

        app_downloads: list[tuple[str, Path]] = []
        apps_to_download: list[SelectedAppMetadata] = []

        for selected_app in selected_apps:
            selected_version = selected_app.selected_version or selected_app.version
            messages.append(
                f"[VERSION_CHECK] Comprobando versión solicitada app_id={selected_app.app_id} "
                f"version={selected_version}."
            )

            if self._find_selected_existing_version(selected_app) is not None:
                messages.append(
                    f"[VERSION_CHECK] Versión ya registrada para {selected_app.title}. "
                    "Se evita descarga APK."
                )
                continue

            messages.append(
                f"[VERSION_CHECK] Versión no registrada o no concreta para {selected_app.title}. "
                "Se requiere APK."
            )
            app_downloads.append(
                (
                    selected_app.app_id,
                    Path(apk_tmp_dir) / comparison_id / selected_app.app_id,
                )
            )
            apps_to_download.append(selected_app)

        if len(app_downloads) == 1:
            messages.append("[APK] Se descargará 1 APK.")
        else:
            messages.append(
                f"[APK] Se descargarán {len(app_downloads)} APKs en paralelo."
            )

        logger.info(
            "[APK] Iniciando descarga de %s APKs para comparison_id=%s",
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
                f"[APK] Descarga completada para app_id={download_info.app_id}: "
                f"{apk_path} ({size_mb:.2f} MB)."
            )
            logger.info(
                "[APK] Descarga completada app_id=%s path=%s size=%.2fMB",
                download_info.app_id,
                apk_path,
                size_mb,
            )

        messages.append("[APK] Descarga finalizada.")
        return apk_paths_by_app_id, messages

    def _save_metadata_without_apk(
        self,
        selected_app: SelectedAppMetadata,
        extracted_metadata: ExtractedApkMetadata,
        existing_application: Application | None,
        initial_messages: list[str] | None = None,
    ) -> PreparedAppVersion:
        messages = list(initial_messages or [])
        app_already_registered = existing_application is not None

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

        if existing_version is None:
            app_version = AppVersion(
                id_app=extracted_metadata.id_app,
                version=extracted_metadata.version,
                fecha_version=extracted_metadata.fecha_version,
                categoria=extracted_metadata.categoria,
                modelo_integracion=extracted_metadata.modelo_integracion,
                version_code=extracted_metadata.version_code,
                apk_sha256=extracted_metadata.apk_sha256,
                ruta_apk=None,
                estado_mobsf=MobSFAnalysisStatus.NOT_ANALYZED,
            )
            saved_version = self.app_version_repository.save(app_version)
            messages.append(
                f"[DB] Nueva versión registrada sin APK local: {saved_version.id_app} "
                f"versión {saved_version.version}."
            )
        else:
            saved_version = existing_version
            messages.append(
                f"[DB] Se reutiliza versión registrada: {saved_version.id_app} "
                f"versión {saved_version.version}."
            )

        return PreparedAppVersion(
            selected_app=selected_app,
            application=saved_application,
            app_version=saved_version,
            apk_path=Path(saved_version.ruta_apk) if saved_version.ruta_apk else None,
            app_already_registered=app_already_registered,
            version_already_registered=version_already_registered,
            messages=messages,
        )

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

        integration_model = (
            existing_application.modelo_integracion_actual
            if existing_application is not None
            else IntegrationModel.UNKNOWN
        )

        logger.info(
            "[METADATA] Se registrará %s usando versión recibida de Google Play: %s",
            selected_app.app_id,
            selected_app.version,
        )

        return ExtractedApkMetadata(
            id_app=selected_app.app_id,
            version=selected_app.version.strip()[:100],
            version_code=selected_app.version_code,
            fecha_version=parse_date_or_none(selected_app.version_date),
            categoria=selected_app.genre,
            modelo_integracion=integration_model,
            apk_sha256=selected_app.apk_sha256,
        )

    def _validate_apk_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise AppRegistrationError(
                f"El archivo APK/XAPK/APKS/APKM no existe: {path}"
            )

        if not os.access(path, os.R_OK):
            raise AppRegistrationError(
                f"El archivo APK/XAPK/APKS/APKM no es legible: {path}"
            )

        if path.suffix.lower() not in SUPPORTED_LOCAL_APK_EXTENSIONS:
            raise AppRegistrationError(
                "Extensión no soportada: "
                f"{path.suffix}. Extensiones válidas: "
                f"{', '.join(sorted(SUPPORTED_LOCAL_APK_EXTENSIONS))}."
            )

    def _validate_manual_apk_path(self, path: Path) -> Path:
        self._validate_apk_file(path)
        allowed_dir = Path(
            os.getenv("MANUAL_APK_UPLOAD_DIR", "/app/artifacts/manual_uploads")
        ).resolve()
        resolved_path = path.resolve()

        if resolved_path != allowed_dir and allowed_dir not in resolved_path.parents:
            raise AppRegistrationError(
                "Ruta local no permitida. El APK debe estar dentro de "
                f"{allowed_dir}. Ruta recibida: {resolved_path}"
            )

        return resolved_path

    def _store_apk(
        self,
        source_path: Path,
        metadata: ExtractedApkMetadata,
        move_source: bool,
        messages: list[str] | None = None,
    ) -> Path:
        storage_dir = Path(os.getenv("APK_STORAGE_DIR", "/app/artifacts/apks"))
        safe_app_id = _safe_path_component(metadata.id_app)
        safe_version = _safe_path_component(metadata.version)
        target_dir = storage_dir / safe_app_id / safe_version
        target_dir.mkdir(parents=True, exist_ok=True)

        sha = (metadata.apk_sha256 or "unknown")[:12]
        target_name = f"{safe_app_id}_{safe_version}_{sha}{source_path.suffix.lower()}"
        target_path = target_dir / target_name

        if source_path.resolve() == target_path.resolve():
            return target_path

        if target_path.exists():
            if move_source and source_path.exists():
                source_path.unlink()
                if messages is not None:
                    messages.append(
                        f"[APK] APK temporal eliminado porque ya existía en almacenamiento gestionado: {source_path}."
                    )
                logger.info(
                    "[APK] APK temporal eliminado porque el destino gestionado ya existía: %s",
                    source_path,
                )
            return target_path

        if move_source:
            shutil.move(str(source_path), str(target_path))
            if messages is not None:
                messages.append(
                    f"[APK] APK temporal movido a almacenamiento gestionado: {target_path}."
                )
            logger.info(
                "[APK] APK temporal movido a almacenamiento gestionado: %s -> %s",
                source_path,
                target_path,
            )
        else:
            shutil.copy2(source_path, target_path)
            if messages is not None:
                messages.append(
                    f"[APK] APK copiado a almacenamiento gestionado: {target_path}."
                )
            logger.info(
                "[APK] APK copiado a almacenamiento gestionado: %s -> %s",
                source_path,
                target_path,
            )

        return target_path

    def _is_valid_managed_apk_path(self, path: Path | None) -> bool:
        if path is None:
            return False

        try:
            resolved_path = path.resolve()
            managed_dir = Path(
                os.getenv("APK_STORAGE_DIR", "/app/artifacts/apks")
            ).resolve()
        except OSError:
            return False

        return (
            resolved_path.exists()
            and resolved_path.is_file()
            and (resolved_path == managed_dir or managed_dir in resolved_path.parents)
        )

    def _cleanup_metadata_extraction_dir(
        self, apk_path: Path, messages: list[str]
    ) -> None:
        extraction_dir = apk_path.parent / "_metadata_extracted"
        if not extraction_dir.exists():
            return

        try:
            shutil.rmtree(extraction_dir)
            messages.append(
                f"[APK] Limpiando directorio temporal de extracción: {extraction_dir}."
            )
            logger.info(
                "[APK] Directorio temporal de extracción eliminado: %s", extraction_dir
            )
        except OSError as exc:
            messages.append(
                f"[APK] No se pudo limpiar directorio temporal de extracción {extraction_dir}: {exc}."
            )
            logger.warning(
                "[APK] No se pudo limpiar directorio temporal de extracción %s: %s",
                extraction_dir,
                exc,
            )

    def _cleanup_download_parent_dirs(
        self, source_path: Path, messages: list[str]
    ) -> None:
        tmp_root = Path(
            os.getenv(
                "APK_TMP_DIR", os.getenv("APK_OUTPUT_DIR", "/app/artifacts/tmp/apks")
            )
        ).resolve()

        current: Path | None = None
        with suppress(OSError):
            current = source_path.parent.resolve()
        if current is None:
            return

        while current != tmp_root and tmp_root in current.parents:
            try:
                current.rmdir()
                messages.append(
                    f"[APK] Directorio temporal de comparación eliminado por estar vacío: {current}."
                )
                logger.info(
                    "[APK] Directorio temporal de comparación eliminado por estar vacío: %s",
                    current,
                )
            except OSError:
                break
            current = current.parent

        if current == tmp_root:
            with suppress(OSError):
                current.rmdir()
                messages.append(
                    f"[APK] Directorio temporal de comparación eliminado por estar vacío: {current}."
                )
                logger.info(
                    "[APK] Directorio temporal raíz eliminado por estar vacío: %s",
                    current,
                )

    def _cleanup_source_file(self, path: Path, messages: list[str]) -> None:
        try:
            if path.exists():
                path.unlink()
                messages.append(f"[DEDUP] Se elimina APK temporal duplicado: {path}.")
                logger.info("[DEDUP] APK temporal duplicado eliminado: %s", path)
                self._cleanup_download_parent_dirs(path, messages)
        except OSError as exc:
            messages.append(
                f"[DEDUP] No se pudo eliminar APK temporal duplicado {path}: {exc}."
            )
            logger.warning(
                "[DEDUP] Error eliminando temporal duplicado %s: %s", path, exc
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


def _is_bad_generated_name(value: str, app_id: str) -> bool:
    normalized = value.strip()
    lower = normalized.lower()
    app_lower = app_id.lower()

    if not normalized:
        return True

    if re.match(r"^[0-9a-f]{16,}[_-]", lower):
        return True

    if "@" in normalized and app_lower in lower:
        return True

    if lower == app_lower:
        return True

    if lower.startswith("upload.") or lower.startswith("manual."):
        return True

    return False


def _selected_app_key(selected_app: SelectedAppMetadata) -> str:
    return "|".join(
        [
            selected_app.app_id,
            selected_app.selected_version or selected_app.version or "",
            selected_app.apk_sha256 or "",
        ]
    )


def _safe_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned[:120] or "unknown"


def _selected_metadata_from_saved(
    application: Application,
    title: str | None,
    version: str,
    version_date: str | None,
) -> SelectedAppMetadata:
    return SelectedAppMetadata(
        app_id=application.id_app,
        title=title or application.nombre,
        developer=application.desarrollador,
        icon=application.icono,
        genre=application.categoria,
        version=version,
        version_date=version_date,
        selected_version=version,
        integration_model=application.modelo_integracion_actual.value,
    )
