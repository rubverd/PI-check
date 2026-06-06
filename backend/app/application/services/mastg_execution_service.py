from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.application.services.app_registration_service import PreparedAppVersion
from app.application.services.mastg_catalog import GLOBAL_INDEX_ID
from app.application.services.privacy_index_service import PrivacyIndexService
from app.domain.entities.mastg_evaluation import MastgEvaluation
from app.domain.entities.privacy_index_result import PrivacyIndexResult
from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.persistence.repositories.mastg_evaluation_repository import MastgEvaluationRepository
from app.infrastructure.persistence.repositories.privacy_index_repository import PrivacyIndexRepository
from app.infrastructure.security.mastg.runner import MastgLiteRunner

logger = logging.getLogger("pi-check")


@dataclass
class MastgExecutionSummary:
    evaluations: list[MastgEvaluation] = field(default_factory=list)
    index_results: list[PrivacyIndexResult] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


class MastgExecutionService:
    def __init__(self, db: Session):
        self.db = db
        self.index_repository = PrivacyIndexRepository(db)
        self.evaluation_repository = MastgEvaluationRepository(db)
        self.index_service = PrivacyIndexService(db)
        self.runner = MastgLiteRunner()
        self.results_dir = Path(
            os.getenv("MASTG_REPORTS_DIR", "/app/artifacts/reports/mastg")
        )

    def execute_for_prepared_app(
        self,
        prepared_app: PreparedAppVersion,
        id_indice: str = GLOBAL_INDEX_ID,
    ) -> MastgExecutionSummary:
        app_version = prepared_app.app_version
        messages: list[str] = []

        if prepared_app.apk_path is None:
            message = (
                f"[MASTG] No se ejecuta MASTG para app_id={app_version.id_app} "
                "porque no hay APK/XAPK/APKS/APKM disponible."
            )
            logger.info(message)
            messages.append(message)
            return MastgExecutionSummary(messages=messages)

        if not prepared_app.apk_path.exists():
            message = f"[MASTG] No existe el artefacto descargado: {prepared_app.apk_path}"
            logger.info(message)
            messages.append(message)
            return MastgExecutionSummary(messages=messages)

        index = self.index_repository.find_by_id(id_indice)
        if index is None or not index.pruebas_mastg:
            message = (
                f"[MASTG] No hay pruebas configuradas para el índice {id_indice}; "
                "se continúa sin ejecutar MASTG-lite."
            )
            logger.info(message)
            messages.append(message)
            return MastgExecutionSummary(messages=messages)

        messages.append(
            f"[MASTG] Ejecutando batería MASTG para app_id={app_version.id_app} "
            f"version={app_version.version}."
        )
        logger.info(
            "[MASTG] Ejecutando batería MASTG para app_id=%s version=%s",
            app_version.id_app,
            app_version.version,
        )

        run_results = self.runner.run_tests(
            artifact_path=prepared_app.apk_path,
            id_app=app_version.id_app,
            version=app_version.version,
            test_ids=index.pruebas_mastg,
        )

        evaluations: list[MastgEvaluation] = []
        for run_result in run_results:
            report_path = self._save_evidence_report(
                id_app=app_version.id_app,
                version=app_version.version,
                id_mastg=run_result.id_mastg,
                payload={
                    "id_app": app_version.id_app,
                    "version": app_version.version,
                    "id_mastg": run_result.id_mastg,
                    "resultado": run_result.status.value,
                    "mensaje": run_result.message,
                    "evidencia": run_result.evidence,
                    "artifact_path": str(prepared_app.apk_path),
                    "fecha_ejecucion": datetime.utcnow().isoformat(),
                },
            )
            evaluation = MastgEvaluation(
                id_app=app_version.id_app,
                version=app_version.version,
                id_mastg=run_result.id_mastg,
                resultado=run_result.status,
                ruta_resultado_json=report_path,
                mensaje_error=run_result.message if run_result.status == MastgResultStatus.ERROR else None,
                fecha_ejecucion=datetime.utcnow(),
            )
            saved = self.evaluation_repository.save(evaluation)
            evaluations.append(saved)
            messages.append(
                f"[MASTG] Resultado {run_result.id_mastg}: {run_result.status.value}."
            )
            messages.append(f"[MASTG] Evidencias guardadas: {report_path}.")
            logger.info("[MASTG] Evidencias guardadas: %s", report_path)

        index_result = self.index_service.calculate_index_result(
            id_indice=id_indice,
            id_app=app_version.id_app,
            version=app_version.version,
        )
        index_results = [index_result] if index_result is not None else []
        for result in index_results:
            messages.append(f"[INDEX] Calculando {result.id_indice}.")
            messages.append(
                f"[INDEX] Resultado: {result.pruebas_superadas}/{result.pruebas_totales} = {result.puntuacion:.3f}."
            )

        return MastgExecutionSummary(
            evaluations=evaluations,
            index_results=index_results,
            messages=messages,
        )

    def _save_evidence_report(
        self,
        id_app: str,
        version: str,
        id_mastg: str,
        payload: dict[str, Any],
    ) -> str:
        output_dir = (
            self.results_dir
            / self._safe_path_part(id_app)
            / self._safe_path_part(version)
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{self._safe_path_part(id_mastg)}.json"
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
        return str(output_path)

    def _safe_path_part(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
        return cleaned or "unknown"
