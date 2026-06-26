from __future__ import annotations

import importlib
import json
import re
import traceback
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.services.mastg.evaluators.base import ensure_rule_result
from app.application.services.mastg.mastg_score_service import MastgScoreService
from app.application.services.mastg.models import (
    MastgEvaluationContext,
    MastgEvaluationStatus,
    MastgRuleResult,
)


class MastgEvaluationService:
    def __init__(
        self,
        session: Session,
        *,
        reports_root: Path | str = Path("/app/artifacts/reports/mastg"),
    ) -> None:
        self.session = session
        self.reports_root = Path(reports_root)
        self.score_service = MastgScoreService()

    def evaluate_version(
        self,
        *,
        index_id: str,
        id_app: str,
        version: str,
    ) -> dict[str, Any]:
        index = self._get_index(index_id)
        version_app = self._get_version_app(id_app=id_app, version=version)
        tests = self._get_tests_for_index(index_id)

        mobsf_json = self._load_mobsf_json(version_app.get("ruta_informe_mobsf"))
        apk_path = self._resolve_existing_path(version_app.get("ruta_apk"))

        report_dir = self._build_report_dir(id_app=id_app, version=version)
        report_dir.mkdir(parents=True, exist_ok=True)

        evaluated_results: list[dict[str, Any]] = []

        for test in tests:
            result = self._run_single_test(
                test=test,
                id_app=id_app,
                version=version,
                mobsf_json=mobsf_json,
                apk_path=apk_path,
                report_dir=report_dir,
            )

            evidence_path = self._write_evidence_json(
                report_dir=report_dir,
                id_mastg=test["id_mastg"],
                result=result,
                test=test,
                id_app=id_app,
                version=version,
                index_id=index_id,
            )

            self._upsert_evaluation_result(
                id_app=id_app,
                version=version,
                id_mastg=test["id_mastg"],
                result=result,
                evidence_path=evidence_path,
            )

            evaluated_results.append(
                {
                    "id_mastg": test["id_mastg"],
                    "nombre": test["nombre"],
                    "categoria_masvs": test.get("categoria_masvs"),
                    "perfil": test.get("perfil"),
                    "origen": test.get("origen"),
                    "tipo_relacion": test.get("tipo_relacion"),
                    "resultado": result.status.value,
                    "summary": result.summary,
                    "recommendation": result.recommendation,
                    "ruta_resultado_json": str(evidence_path),
                    "mensaje_error": result.error,
                }
            )

        self.session.commit()

        score = self.score_service.calculate(evaluated_results)

        return {
            "index": index,
            "version": {
                "id_app": id_app,
                "version": version,
                "ruta_apk": version_app.get("ruta_apk"),
                "ruta_informe_mobsf": version_app.get("ruta_informe_mobsf"),
                "has_apk": apk_path is not None,
                "has_mobsf_json": mobsf_json is not None,
            },
            "score": score,
            "results": evaluated_results,
        }

    def _get_index(self, index_id: str) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    id_indice,
                    nombre,
                    descripcion,
                    ruta_del_script
                FROM indice_privacidad
                WHERE id_indice = :index_id
                """
            ),
            {"index_id": index_id},
        ).mappings().first()

        if row is None:
            raise ValueError(f"No existe el índice de privacidad: {index_id}")

        return dict(row)

    def _get_version_app(self, *, id_app: str, version: str) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    id_app,
                    version,
                    version_code,
                    fecha_version,
                    apk_sha256,
                    ruta_apk,
                    estado_mobsf,
                    hash_mobsf,
                    ruta_informe_mobsf
                FROM version_app
                WHERE id_app = :id_app
                  AND version = :version
                """
            ),
            {
                "id_app": id_app,
                "version": version,
            },
        ).mappings().first()

        if row is None:
            raise ValueError(
                f"No existe version_app para id_app={id_app!r}, version={version!r}"
            )

        return dict(row)

    def _get_tests_for_index(self, index_id: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    pm.id_mastg,
                    pm.nombre,
                    pm.descripcion,
                    pm.referencia_script_implementacion,
                    pm.categoria_masvs,
                    pm.perfil,
                    pm.origen,
                    pm.tipo_relacion
                FROM formar_parte fp
                JOIN prueba_mastg pm ON pm.id_mastg = fp.id_mastg
                WHERE fp.id_indice = :index_id
                ORDER BY pm.id_mastg
                """
            ),
            {"index_id": index_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    def _run_single_test(
        self,
        *,
        test: dict[str, Any],
        id_app: str,
        version: str,
        mobsf_json: dict[str, Any] | None,
        apk_path: Path | None,
        report_dir: Path,
    ) -> MastgRuleResult:
        id_mastg = test["id_mastg"]
        module_path = test.get("referencia_script_implementacion")

        if not module_path:
            return MastgRuleResult(
                status=MastgEvaluationStatus.NOT_EXECUTED,
                summary="La prueba no tiene módulo de implementación asociado.",
                details={
                    "id_mastg": id_mastg,
                    "nombre": test.get("nombre"),
                },
            )

        context = MastgEvaluationContext(
            id_app=id_app,
            version=version,
            id_mastg=id_mastg,
            mobsf_json=mobsf_json,
            apk_path=apk_path,
            report_dir=report_dir,
            metadata={
                "test": test,
            },
        )

        try:
            module = importlib.import_module(str(module_path))
            evaluate = getattr(module, "evaluate", None)

            if evaluate is None:
                return MastgRuleResult.error_result(
                    "El módulo del evaluador no expone una función evaluate(context).",
                    error=f"Missing evaluate function in module {module_path}",
                    details={
                        "id_mastg": id_mastg,
                        "module_path": module_path,
                    },
                )

            raw_result = evaluate(context)
            return ensure_rule_result(raw_result)

        except Exception as exc:
            return MastgRuleResult.error_result(
                "Error técnico durante la ejecución del evaluador.",
                error=str(exc),
                details={
                    "id_mastg": id_mastg,
                    "module_path": module_path,
                    "traceback": traceback.format_exc(),
                },
            )

    def _write_evidence_json(
        self,
        *,
        report_dir: Path,
        id_mastg: str,
        result: MastgRuleResult,
        test: dict[str, Any],
        id_app: str,
        version: str,
        index_id: str,
    ) -> Path:
        path = report_dir / f"{self._safe_path_component(id_mastg)}.json"

        payload = {
            "id_app": id_app,
            "version": version,
            "index_id": index_id,
            "test": test,
            "result": result.to_json_dict(),
        }

        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        return path

    def _upsert_evaluation_result(
        self,
        *,
        id_app: str,
        version: str,
        id_mastg: str,
        result: MastgRuleResult,
        evidence_path: Path,
    ) -> None:
        self.session.execute(
            text(
                """
                INSERT INTO evaluar (
                    id_app,
                    version,
                    id_mastg,
                    resultado,
                    ruta_resultado_json,
                    mensaje_error,
                    fecha_ejecucion
                )
                VALUES (
                    :id_app,
                    :version,
                    :id_mastg,
                    :resultado,
                    :ruta_resultado_json,
                    :mensaje_error,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (id_app, version, id_mastg)
                DO UPDATE SET
                    resultado = EXCLUDED.resultado,
                    ruta_resultado_json = EXCLUDED.ruta_resultado_json,
                    mensaje_error = EXCLUDED.mensaje_error,
                    fecha_ejecucion = EXCLUDED.fecha_ejecucion
                """
            ),
            {
                "id_app": id_app,
                "version": version,
                "id_mastg": id_mastg,
                "resultado": result.status.value,
                "ruta_resultado_json": str(evidence_path),
                "mensaje_error": result.error,
            },
        )

    def _load_mobsf_json(self, raw_path: str | None) -> dict[str, Any] | None:
        path = self._resolve_existing_path(raw_path)

        if path is None:
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _resolve_existing_path(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None

        path = Path(raw_path)

        if path.exists():
            return path

        return None

    def _build_report_dir(self, *, id_app: str, version: str) -> Path:
        return (
            self.reports_root
            / self._safe_path_component(id_app)
            / self._safe_path_component(version)
        )

    def _safe_path_component(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
        return cleaned.strip("._") or "unknown"
