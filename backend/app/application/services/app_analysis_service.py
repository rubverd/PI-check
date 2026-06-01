import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.entities.application import Application
from app.domain.entities.app_version import AppVersion
from app.domain.entities.mobsf_report import MobSFReport
from app.domain.entities.version_report import VersionReport
from app.domain.value_objects.integration_model import IntegrationModel
from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus
from app.infrastructure.external.apkeep_client import download_apk_with_apkeep
from app.infrastructure.external.apk_metadata_extractor import extract_apk_metadata
from app.infrastructure.external.mobsf_client import MobSFClient, MobSFClientError
from app.infrastructure.persistence.repositories.application_repository import (
    ApplicationRepository,
)
from app.infrastructure.persistence.repositories.app_version_repository import (
    AppVersionRepository,
)
from app.infrastructure.storage.report_storage import ReportStorage
from app.schemas.comparisons import SelectedAppMetadata


class AppAnalysisError(Exception):
    """Error controlado durante el análisis de una aplicación."""


class AppAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.application_repository = ApplicationRepository(db)
        self.app_version_repository = AppVersionRepository(db)
        self.report_storage = ReportStorage()
        self.mobsf_client = MobSFClient()

    def ensure_version_report_with_mobsf(
        self,
        selected_app: SelectedAppMetadata,
        comparison_id: str,
    ) -> tuple[VersionReport, list[str]]:
        messages: list[str] = []

        reusable_version = self.app_version_repository.find_latest_with_mobsf_report(
            selected_app.app_id
        )

        if reusable_version is not None:
            loaded_report = self._load_existing_mobsf_report(reusable_version)

            if loaded_report is not None:
                messages.append(
                    f"Se reutiliza informe MobSF existente para {selected_app.title} "
                    f"versión {reusable_version.version}."
                )

                return (
                    VersionReport(
                        version_app=reusable_version,
                        mobsf_report=loaded_report,
                    ),
                    messages,
                )

            messages.append(
                f"Existe referencia a informe MobSF para {selected_app.title}, "
                "pero no se ha podido cargar el JSON. Se generará de nuevo."
            )

        messages.append(
            f"No existe informe MobSF reutilizable para {selected_app.title}. "
            "Se descargará el APK."
        )

        apk_path = self._download_selected_app_apk(
            selected_app=selected_app,
            comparison_id=comparison_id,
        )

        extracted_metadata = extract_apk_metadata(
            apk_path=apk_path,
            fallback_app_id=selected_app.app_id,
            fallback_version=selected_app.version,
            fallback_category=selected_app.genre,
            fallback_version_date=selected_app.version_date,
        )

        application = Application(
            id_app=extracted_metadata.id_app,
            nombre=selected_app.title,
            icono=selected_app.icon,
            categoria=selected_app.genre or extracted_metadata.categoria,
            desarrollador=selected_app.developer,
            modelo_integracion_actual=extracted_metadata.modelo_integracion,
        )

        saved_application = self.application_repository.save(application)

        messages.append(
            f"Aplicación registrada/actualizada en BD: {saved_application.id_app}."
        )

        app_version = self.app_version_repository.find_by_id(
            id_app=extracted_metadata.id_app,
            version=extracted_metadata.version,
        )

        if app_version is None:
            app_version = AppVersion(
                id_app=extracted_metadata.id_app,
                version=extracted_metadata.version,
                version_code=extracted_metadata.version_code,
                fecha_version=extracted_metadata.fecha_version,
                categoria=extracted_metadata.categoria,
                modelo_integracion=extracted_metadata.modelo_integracion,
                apk_sha256=extracted_metadata.apk_sha256,
                estado_mobsf=MobSFAnalysisStatus.NOT_ANALYZED,
            )

            app_version = self.app_version_repository.save(app_version)

            messages.append(
                f"Versión registrada en BD: {app_version.id_app} "
                f"versión {app_version.version}."
            )

        else:
            app_version.apk_sha256 = extracted_metadata.apk_sha256
            app_version.modelo_integracion = extracted_metadata.modelo_integracion
            app_version.version_code = extracted_metadata.version_code
            app_version.fecha_version = extracted_metadata.fecha_version
            app_version.categoria = extracted_metadata.categoria

            app_version = self.app_version_repository.save(app_version)

            messages.append(
                f"Versión existente actualizada en BD: {app_version.id_app} "
                f"versión {app_version.version}."
            )

        if (
            app_version.estado_mobsf == MobSFAnalysisStatus.SUCCESS
            and app_version.ruta_informe_mobsf
        ):
            loaded_report = self._load_existing_mobsf_report(app_version)

            if loaded_report is not None:
                messages.append(
                    f"La versión {app_version.version} ya tenía informe MobSF válido."
                )

                return (
                    VersionReport(
                        version_app=app_version,
                        mobsf_report=loaded_report,
                    ),
                    messages,
                )

        app_version.estado_mobsf = MobSFAnalysisStatus.PENDING
        app_version = self.app_version_repository.save(app_version)

        messages.append(
            f"Se inicia análisis MobSF para {app_version.id_app} "
            f"versión {app_version.version}."
        )

        try:
            mobsf_report = self.mobsf_client.generate_json_report(apk_path)

        except MobSFClientError as exc:
            app_version.estado_mobsf = MobSFAnalysisStatus.ERROR
            self.app_version_repository.save(app_version)

            raise AppAnalysisError(
                f"Error generando informe MobSF para {selected_app.title}: {exc}"
            ) from exc

        report_path = self.report_storage.save_mobsf_report(
            id_app=app_version.id_app,
            version=app_version.version,
            report_data=mobsf_report.json_report,
        )

        mobsf_report.ruta_informe = report_path

        app_version = self.app_version_repository.update_mobsf_report(
            id_app=app_version.id_app,
            version=app_version.version,
            hash_mobsf=mobsf_report.hash_mobsf,
            ruta_informe_mobsf=report_path,
            estado_mobsf=MobSFAnalysisStatus.SUCCESS,
        )

        messages.append(
            f"Informe MobSF generado y registrado para {app_version.id_app} "
            f"versión {app_version.version}."
        )

        return (
            VersionReport(
                version_app=app_version,
                mobsf_report=mobsf_report,
            ),
            messages,
        )

    def _load_existing_mobsf_report(
        self,
        app_version: AppVersion,
    ) -> MobSFReport | None:
        report_data = self.report_storage.load_mobsf_report(
            app_version.ruta_informe_mobsf
        )

        if report_data is None:
            return None

        if not app_version.hash_mobsf:
            return None

        return MobSFReport(
            hash_mobsf=app_version.hash_mobsf,
            file_name=None,
            scan_type=None,
            ruta_informe=app_version.ruta_informe_mobsf,
            json_report=report_data,
        )

    def _download_selected_app_apk(
        self,
        selected_app: SelectedAppMetadata,
        comparison_id: str,
    ) -> Path:
        apk_tmp_dir = os.getenv(
            "APK_TMP_DIR",
            os.getenv("APK_OUTPUT_DIR", "/app/artifacts/tmp/apks"),
        )

        output_dir = Path(apk_tmp_dir) / comparison_id / selected_app.app_id

        download_info = download_apk_with_apkeep(
            app_id=selected_app.app_id,
            output_dir=output_dir,
            source="apk-pure",
            timeout_seconds=300,
        )

        if not download_info.success:
            raise AppAnalysisError(
                f"No se pudo descargar el APK de {selected_app.title}: "
                f"{download_info.error}"
            )

        apk_path = self._select_analysis_file(download_info.apk_files)

        if apk_path is None:
            raise AppAnalysisError(
                f"La descarga de {selected_app.title} finalizó, "
                "pero no se encontró ningún APK/XAPK/APKS/APKM."
            )

        return apk_path

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