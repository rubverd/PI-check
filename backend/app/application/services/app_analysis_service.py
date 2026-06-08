import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.application.services.app_registration_service import PreparedAppVersion
from app.domain.entities.mobsf_report import MobSFReport
from app.domain.entities.version_report import VersionReport
from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus
from app.infrastructure.external.mobsf_client import MobSFClient, MobSFClientError
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.repositories.application_repository import (
    ApplicationRepository,
)
from app.infrastructure.persistence.repositories.app_version_repository import (
    AppVersionRepository,
)
from app.infrastructure.storage.report_storage import ReportStorage
from app.schemas.comparisons import SelectedAppMetadata

logger = logging.getLogger("pi-check")


@dataclass(frozen=True)
class MobSFAnalysisReference:
    id_app: str
    version: str
    selected_app: SelectedAppMetadata
    apk_path: str | None


class AppAnalysisError(Exception):
    """Error controlado durante el análisis de una aplicación."""


class AppAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.app_version_repository = AppVersionRepository(db)
        self.report_storage = ReportStorage()
        self.mobsf_client = MobSFClient()

    def ensure_mobsf_reports(
        self,
        prepared_apps: list[PreparedAppVersion],
    ) -> list[tuple[VersionReport, list[str]]]:
        references = [
            self._to_analysis_reference(prepared) for prepared in prepared_apps
        ]
        analysis_mode = os.getenv("MOBSF_ANALYSIS_MODE", "sync").strip().lower()
        max_parallel = max(1, int(os.getenv("MOBSF_MAX_PARALLEL_ANALYSES", "2")))

        logger.info(
            "[MOBSF] Modo de análisis: %s max_parallel=%s versiones=%s",
            analysis_mode,
            max_parallel,
            len(references),
        )

        if analysis_mode == "parallel" and len(references) > 1:
            logger.info(
                "[MOBSF] Versiones recibidas para análisis paralelo: %s",
                len(references),
            )
            return self._ensure_mobsf_reports_parallel(references, max_parallel)

        results: list[tuple[VersionReport, list[str]]] = []
        for reference in references:
            results.append(_ensure_mobsf_report_in_new_session(reference))
        return results

    def _ensure_mobsf_reports_parallel(
        self,
        references: list[MobSFAnalysisReference],
        max_parallel: int,
    ) -> list[tuple[VersionReport, list[str]]]:
        results_by_index: dict[int, tuple[VersionReport, list[str]]] = {}
        worker_count = min(max_parallel, len(references))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_ensure_mobsf_report_in_new_session, reference): index
                for index, reference in enumerate(references)
            }

            for future in as_completed(futures):
                index = futures[future]
                reference = references[index]
                logger.info(
                    "[MOBSF] Recibido resultado de análisis paralelo app_id=%s version=%s",
                    reference.id_app,
                    reference.version,
                )
                results_by_index[index] = future.result()

        return [results_by_index[index] for index in range(len(references))]

    def _to_analysis_reference(
        self,
        prepared_app: PreparedAppVersion,
    ) -> MobSFAnalysisReference:
        return MobSFAnalysisReference(
            id_app=prepared_app.app_version.id_app,
            version=prepared_app.app_version.version,
            selected_app=prepared_app.selected_app,
            apk_path=str(prepared_app.apk_path) if prepared_app.apk_path else None,
        )

    def ensure_mobsf_report(
        self,
        prepared_app: PreparedAppVersion,
    ) -> tuple[VersionReport, list[str]]:
        messages: list[str] = []

        app_version = prepared_app.app_version
        selected_app = prepared_app.selected_app

        logger.info(
            "[MOBSF] Comprobando informe para app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )

        messages.append(
            f"[MOBSF] Comprobando informe para {selected_app.title} "
            f"versión {app_version.version}."
        )

        reusable_report = self._find_reusable_mobsf_report(app_version, messages)
        if reusable_report is not None:
            return (
                VersionReport(
                    version_app=reusable_report.version_app,
                    mobsf_report=reusable_report.mobsf_report,
                ),
                messages,
            )

        if prepared_app.apk_path is None:
            messages.append(
                f"[MOBSF] No se lanza MobSF para {selected_app.title}: "
                "no hay APK disponible."
            )

            logger.info(
                "[MOBSF] No se lanza análisis para app_id=%s: apk_path=None",
                app_version.id_app,
            )

            return (
                VersionReport(
                    version_app=app_version,
                    mobsf_report=None,
                ),
                messages,
            )

        apk_path = prepared_app.apk_path

        if not apk_path.exists():
            raise AppAnalysisError(
                f"No existe el archivo APK/XAPK para analizar con MobSF: {apk_path}"
            )

        max_apk_size_mb = int(os.getenv("MAX_APK_SIZE_MB", "40"))
        apk_size_mb = apk_path.stat().st_size / (1024 * 1024)

        messages.append(
            f"[MOBSF] Tamaño del archivo para {selected_app.title}: "
            f"{apk_size_mb:.2f} MB. Límite configurado: {max_apk_size_mb} MB."
        )

        logger.info(
            "[MOBSF] app_id=%s apk_size=%.2fMB max_size=%sMB",
            app_version.id_app,
            apk_size_mb,
            max_apk_size_mb,
        )

        if apk_size_mb > max_apk_size_mb:
            app_version.estado_mobsf = MobSFAnalysisStatus.NOT_ANALYZED
            app_version = self.app_version_repository.save(app_version)
            self.db.commit()
            logger.info(
                "[DB] Commit de estado NOT_ANALYZED completado app_id=%s version=%s",
                app_version.id_app,
                app_version.version,
            )

            messages.append(
                f"[MOBSF] No se lanza MobSF para {selected_app.title}: "
                f"el archivo supera el límite de {max_apk_size_mb} MB."
            )

            logger.warning(
                "[MOBSF] Análisis omitido por tamaño. app_id=%s version=%s size=%.2fMB",
                app_version.id_app,
                app_version.version,
                apk_size_mb,
            )

            return (
                VersionReport(
                    version_app=app_version,
                    mobsf_report=None,
                ),
                messages,
            )

        app_version.estado_mobsf = MobSFAnalysisStatus.PENDING
        app_version = self.app_version_repository.save(app_version)
        self.db.commit()

        messages.append(
            f"[MOBSF] Se inicia análisis MobSF para {app_version.id_app} "
            f"versión {app_version.version}."
        )
        messages.append(
            f"[DB] Commit de estado PENDING completado app_id={app_version.id_app} "
            f"version={app_version.version}."
        )
        logger.info(
            "[MOBSF] Estado actualizado a PENDING app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )
        logger.info(
            "[DB] Commit de estado PENDING completado app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )
        logger.info(
            "[MOBSF] Lanzando análisis tras commit de registro app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )

        try:
            mobsf_report = self.mobsf_client.generate_json_report(apk_path)

        except MobSFClientError as exc:
            app_version.estado_mobsf = MobSFAnalysisStatus.ERROR
            self.app_version_repository.save(app_version)
            self.db.commit()

            logger.exception(
                "[MOBSF] Análisis fallido app_id=%s version=%s",
                app_version.id_app,
                app_version.version,
            )
            logger.info(
                "[DB] Commit de estado ERROR completado app_id=%s version=%s",
                app_version.id_app,
                app_version.version,
            )

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
        self.db.commit()

        messages.append(
            f"[MOBSF] Informe generado y registrado para {app_version.id_app} "
            f"versión {app_version.version}."
        )

        logger.info(
            "[MOBSF] Análisis completado app_id=%s version=%s hash=%s path=%s",
            app_version.id_app,
            app_version.version,
            mobsf_report.hash_mobsf,
            report_path,
        )
        logger.info(
            "[DB] Commit de resultado MobSF completado app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )

        return (
            VersionReport(
                version_app=app_version,
                mobsf_report=mobsf_report,
            ),
            messages,
        )

    def _find_reusable_mobsf_report(
        self,
        app_version,
        messages: list[str],
    ) -> VersionReport | None:
        if (
            app_version.estado_mobsf == MobSFAnalysisStatus.SUCCESS
            and app_version.ruta_informe_mobsf
            and app_version.hash_mobsf
        ):
            loaded_report = self._load_existing_mobsf_report(app_version)
            if loaded_report is not None:
                messages.append(
                    "[MOBSF] Reutilizando informe existente por versión exacta."
                )
                logger.info(
                    "[MOBSF] Reutilizando informe existente por versión exacta app_id=%s version=%s path=%s",
                    app_version.id_app,
                    app_version.version,
                    app_version.ruta_informe_mobsf,
                )
                self.db.commit()
                logger.info(
                    "[DB] Commit de reutilización MobSF completado app_id=%s version=%s",
                    app_version.id_app,
                    app_version.version,
                )
                return VersionReport(
                    version_app=app_version, mobsf_report=loaded_report
                )

            messages.append(
                "[MOBSF] La versión estaba marcada como SUCCESS, pero el informe no existe o no se puede cargar."
            )

        canonical_report = self.report_storage.mobsf_report_path(
            id_app=app_version.id_app,
            version=app_version.version,
        )
        canonical_data = self.report_storage.load_mobsf_report(str(canonical_report))
        if canonical_data is not None:
            hash_mobsf = app_version.hash_mobsf or app_version.apk_sha256 or "unknown"
            updated_version = self.app_version_repository.update_mobsf_report(
                id_app=app_version.id_app,
                version=app_version.version,
                hash_mobsf=hash_mobsf,
                ruta_informe_mobsf=str(canonical_report),
                estado_mobsf=MobSFAnalysisStatus.SUCCESS,
            )
            messages.append(
                "[MOBSF] Informe encontrado en ruta canónica. Se actualiza BD y se reutiliza."
            )
            logger.info(
                "[MOBSF] Informe canónico reutilizado app_id=%s version=%s path=%s",
                app_version.id_app,
                app_version.version,
                canonical_report,
            )
            self.db.commit()
            logger.info(
                "[DB] Commit de reutilización MobSF completado app_id=%s version=%s",
                updated_version.id_app,
                updated_version.version,
            )
            return VersionReport(
                version_app=updated_version,
                mobsf_report=MobSFReport(
                    hash_mobsf=hash_mobsf,
                    file_name=None,
                    scan_type=None,
                    ruta_informe=str(canonical_report),
                    json_report=canonical_data,
                ),
            )

        if app_version.apk_sha256:
            matching_version = (
                self.app_version_repository.find_success_with_mobsf_by_apk_sha256(
                    apk_sha256=app_version.apk_sha256,
                    exclude_id_app=app_version.id_app,
                    exclude_version=app_version.version,
                )
            )
            if matching_version is not None:
                matching_report = self._load_existing_mobsf_report(matching_version)
                if matching_report is not None:
                    canonical_report.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(matching_report.ruta_informe, canonical_report)
                    updated_version = self.app_version_repository.update_mobsf_report(
                        id_app=app_version.id_app,
                        version=app_version.version,
                        hash_mobsf=matching_report.hash_mobsf,
                        ruta_informe_mobsf=str(canonical_report),
                        estado_mobsf=MobSFAnalysisStatus.SUCCESS,
                    )
                    messages.append(
                        "[MOBSF] Reutilizando informe por apk_sha256 coincidente."
                    )
                    logger.info(
                        "[MOBSF] Informe reutilizado por apk_sha256 app_id=%s version=%s source=%s target=%s",
                        app_version.id_app,
                        app_version.version,
                        matching_report.ruta_informe,
                        canonical_report,
                    )
                    matching_report.ruta_informe = str(canonical_report)
                    self.db.commit()
                    logger.info(
                        "[DB] Commit de reutilización MobSF por hash completado app_id=%s version=%s",
                        updated_version.id_app,
                        updated_version.version,
                    )
                    return VersionReport(
                        version_app=updated_version,
                        mobsf_report=matching_report,
                    )

        messages.append(
            "[MOBSF] No existe informe reutilizable. Se lanza análisis MobSF si hay APK disponible."
        )
        logger.info(
            "[MOBSF] No existe informe reutilizable app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )
        return None

    def _prepared_from_reference(
        self,
        reference: MobSFAnalysisReference,
    ) -> PreparedAppVersion:
        app_version = self.app_version_repository.find_by_id(
            id_app=reference.id_app,
            version=reference.version,
        )
        if app_version is None:
            raise AppAnalysisError(
                f"No existe VERSION_APP para id_app={reference.id_app}, version={reference.version}"
            )

        application = ApplicationRepository(self.db).find_by_id(reference.id_app)
        if application is None:
            raise AppAnalysisError(
                f"No existe Aplicación para id_app={reference.id_app}"
            )

        return PreparedAppVersion(
            selected_app=reference.selected_app,
            application=application,
            app_version=app_version,
            apk_path=Path(reference.apk_path) if reference.apk_path else None,
            app_already_registered=True,
            version_already_registered=True,
            messages=[],
        )

    def _load_existing_mobsf_report(
        self,
        app_version,
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


def _ensure_mobsf_report_in_new_session(
    reference: MobSFAnalysisReference,
) -> tuple[VersionReport, list[str]]:
    logger.info(
        "[MOBSF] Lanzando análisis paralelo/aislado app_id=%s version=%s",
        reference.id_app,
        reference.version,
    )

    with SessionLocal() as db:
        service = AppAnalysisService(db)
        try:
            prepared_app = service._prepared_from_reference(reference)
            result = service.ensure_mobsf_report(prepared_app)
            logger.info(
                "[MOBSF] Análisis paralelo/aislado completado app_id=%s version=%s",
                reference.id_app,
                reference.version,
            )
            return result
        except Exception:
            db.rollback()
            logger.exception(
                "[MOBSF] Análisis paralelo/aislado fallido app_id=%s version=%s",
                reference.id_app,
                reference.version,
            )
            raise
