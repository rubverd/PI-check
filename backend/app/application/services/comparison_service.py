import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.application.services.app_analysis_service import AppAnalysisService
from app.application.services.app_registration_service import (
    AppRegistrationService,
    PreparedAppVersion,
    _selected_app_key,
)
from app.domain.entities.comparison_result import ComparisonResult
from app.domain.entities.version_report import VersionReport
from app.schemas.comparisons import ComparisonRequest

logger = logging.getLogger("pi-check")


@dataclass
class ComparisonExecutionResult:
    comparison_id: str
    status: str
    message: str
    messages: list[str]
    comparison: ComparisonResult
    comparison_payload: dict[str, Any]
    comparison_json: str
    comparison_artifact_path: str | None


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

        comparison_payload = _build_comparison_payload(
            comparison_id=comparison_id,
            prepared_a=prepared_a,
            prepared_b=prepared_b,
            report_a=report_a,
            report_b=report_b,
        )
        comparison_json = json.dumps(
            comparison_payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        artifact_path = _save_temporary_comparison_payload(comparison_payload)

        messages.append("[COMPARISON] Comparativa estructurada generada a partir de informes MobSF.")
        messages.append(f"[COMPARISON] Comparativa temporal guardada en {artifact_path}.")
        logger.info(
            "[COMPARISON] Comparativa generada comparison_id=%s left=%s:%s right=%s:%s",
            comparison_id,
            report_a.version_app.id_app,
            report_a.version_app.version,
            report_b.version_app.id_app,
            report_b.version_app.version,
        )
        logger.info("[COMPARISON] Comparativa temporal guardada en %s", artifact_path)

        return ComparisonExecutionResult(
            comparison_id=comparison_id,
            status="completed",
            message="Comparativa generada correctamente.",
            messages=messages,
            comparison=comparison,
            comparison_payload=comparison_payload,
            comparison_json=comparison_json,
            comparison_artifact_path=artifact_path,
        )


def _build_comparison_payload(
    comparison_id: str,
    prepared_a: PreparedAppVersion,
    prepared_b: PreparedAppVersion,
    report_a: VersionReport,
    report_b: VersionReport,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    left = _comparison_side(prepared_a, report_a)
    right = _comparison_side(prepared_b, report_b)
    left_report = report_a.mobsf_report.json_report if report_a.mobsf_report else None
    right_report = report_b.mobsf_report.json_report if report_b.mobsf_report else None

    logger.info(
        "[COMPARISON] Informe MobSF cargado left_available=%s right_available=%s left_keys=%s right_keys=%s",
        left["mobsf_status"],
        right["mobsf_status"],
        sorted(left_report.keys())[:20] if isinstance(left_report, dict) else [],
        sorted(right_report.keys())[:20] if isinstance(right_report, dict) else [],
    )

    return {
        "comparison_id": comparison_id,
        "created_at": created_at.isoformat(),
        "left": left,
        "right": right,
        "summary": {
            "left_model": report_a.version_app.modelo_integracion.value,
            "right_model": report_b.version_app.modelo_integracion.value,
            "same_application": report_a.version_app.id_app == report_b.version_app.id_app,
            "comparison_type": "version_vs_version"
            if report_a.version_app.id_app == report_b.version_app.id_app
            else "app_vs_app",
        },
        "mobsf": {
            "left": _mobsf_summary(report_a),
            "right": _mobsf_summary(report_b),
        },
        "raw_mobsf_highlights": {
            "left": _mobsf_highlights(left_report),
            "right": _mobsf_highlights(right_report),
        },
    }


def _comparison_side(
    prepared: PreparedAppVersion,
    report: VersionReport,
) -> dict[str, Any]:
    version = report.version_app
    return {
        "app_id": version.id_app,
        "name": prepared.application.nombre,
        "version": version.version,
        "version_code": version.version_code,
        "integration_model": version.modelo_integracion.value,
        "mobsf_status": version.estado_mobsf.value,
        "mobsf_report_path": version.ruta_informe_mobsf,
        "apk_sha256": version.apk_sha256,
        "ruta_apk": version.ruta_apk,
    }


def _mobsf_summary(report: VersionReport) -> dict[str, Any]:
    mobsf_report = report.mobsf_report
    json_report = mobsf_report.json_report if mobsf_report else None
    return {
        "available": mobsf_report is not None,
        "hash": mobsf_report.hash_mobsf if mobsf_report else None,
        "report_path": mobsf_report.ruta_informe if mobsf_report else None,
        "file_name": mobsf_report.file_name if mobsf_report else None,
        "scan_type": mobsf_report.scan_type if mobsf_report else None,
        "report_keys": sorted(json_report.keys()) if isinstance(json_report, dict) else [],
    }


def _mobsf_highlights(report_data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report_data, dict):
        return {}

    preferred_keys = [
        "app_name",
        "package_name",
        "version_name",
        "target_sdk",
        "min_sdk",
        "max_sdk",
        "permissions",
        "certificate_analysis",
        "manifest_analysis",
        "code_analysis",
        "binary_analysis",
        "security_score",
        "trackers",
        "domains",
        "urls",
        "emails",
    ]
    return {key: report_data[key] for key in preferred_keys if key in report_data}


def _save_temporary_comparison_payload(payload: dict[str, Any]) -> str:
    output_dir = Path(os.getenv("COMPARISON_ARTIFACTS_DIR", "/app/artifacts/comparisons"))
    output_dir.mkdir(parents=True, exist_ok=True)

    created_at = datetime.fromisoformat(payload["created_at"])
    timestamp = created_at.strftime("%Y%m%d_%H%M%S")
    left = payload["left"]
    right = payload["right"]
    filename = (
        f"{timestamp}_{_safe_filename_part(left['app_id'])}_{_safe_filename_part(left['version'])}"
        f"_vs_{_safe_filename_part(right['app_id'])}_{_safe_filename_part(right['version'])}.json"
    )
    output_path = output_dir / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=str)

    return str(output_path)


def _safe_filename_part(value: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "unknown").strip())
    return cleaned[:80] or "unknown"
