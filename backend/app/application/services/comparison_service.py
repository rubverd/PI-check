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
from app.application.services.mastg.mastg_evaluation_service import MastgEvaluationService
from app.application.services.app_analysis_service import AppAnalysisService
from app.application.services.app_registration_service import (
    AppRegistrationService,
    PreparedAppVersion,
    _selected_app_key,
)
from app.domain.entities.comparison_result import ComparisonResult
from app.core.public_urls import build_public_artifact_url
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
    dashboard_payload: dict[str, Any]
    technical_summary: dict[str, Any]
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
        dashboard_payload = _build_dashboard_payload(
            prepared_a=prepared_a,
            prepared_b=prepared_b,
            report_a=report_a,
            report_b=report_b,
            comparison_payload=comparison_payload,
        )
        technical_summary = _build_technical_summary(report_a, report_b)
        
        mastg_payload = _evaluate_mastg_for_comparison(
            db=self.db,
            report_a=report_a,
            report_b=report_b,
            index_id="picheck_mhealth_v1",
            messages=messages,
        )
        _apply_mastg_to_dashboard(dashboard_payload, mastg_payload)
        comparison.id_indice_aplicado = mastg_payload.get("index_id")

        artifact_path = _save_temporary_comparison_payload(
            comparison_payload,
            dashboard_payload,
            technical_summary,
        )
        response_artifact = {
            "comparison": comparison_payload,
            "dashboard": dashboard_payload,
            "technical_summary": technical_summary,
            "comparison_artifact_path": artifact_path,
        }
        comparison_json = json.dumps(
            response_artifact,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        messages.append("[COMPARISON] Comparativa resumida generada.")
        messages.append(f"[COMPARISON] Artefacto temporal guardado en {artifact_path}.")
        messages.append("[COMPARISON] Respuesta enviada sin informes MobSF completos.")
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
            dashboard_payload=dashboard_payload,
            technical_summary=technical_summary,
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
        "mobsf_highlights": {
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

    urls = _collection_items(report_data.get("urls")) if "urls" in report_data else []
    domains = _collection_items(report_data.get("domains")) if "domains" in report_data else []
    trackers = _collection_items(report_data.get("trackers")) or _collection_items(
        report_data.get("trackers_info")
    )
    permissions = report_data.get("permissions")
    findings = _technical_findings(report_data, "summary")

    return {
        "app_name": _safe_scalar(report_data.get("app_name")),
        "package_name": _safe_scalar(report_data.get("package_name")),
        "version_name": _safe_scalar(report_data.get("version_name")),
        "target_sdk": _safe_scalar(report_data.get("target_sdk")),
        "min_sdk": _safe_scalar(report_data.get("min_sdk")),
        "security_score": _safe_scalar(report_data.get("security_score")),
        "total_permissions": _collection_count(permissions),
        "total_trackers": len(trackers),
        "total_domains": len(domains),
        "total_urls": len(urls),
        "total_findings": len(findings),
        "domain_examples": _string_examples(domains),
        "url_examples": _string_examples(urls),
        "tracker_examples": _string_examples(trackers),
    }


def _build_dashboard_payload(
    prepared_a: PreparedAppVersion,
    prepared_b: PreparedAppVersion,
    report_a: VersionReport,
    report_b: VersionReport,
    comparison_payload: dict[str, Any],
) -> dict[str, Any]:
    left_report = report_a.mobsf_report.json_report if report_a.mobsf_report else None
    right_report = report_b.mobsf_report.json_report if report_b.mobsf_report else None
    left_metrics = _extract_dashboard_metrics(left_report)
    right_metrics = _extract_dashboard_metrics(right_report)

    privacy_metrics = _metric_rows(
        [
            ("Permisos peligrosos", "dangerous_permissions"),
            ("Permisos Health Connect", "health_connect_permissions", "context"),
            ("Permisos de ubicación", "location_permissions", "lower"),
            ("Permisos sensores/salud legacy", "sensor_permissions", "context"),
            ("Permisos almacenamiento/media", "storage_permissions", "lower"),
            ("Trackers", "trackers", "lower"),
        ],
        left_metrics,
        right_metrics,
    )
    security_metrics = _metric_rows(
        [
            ("Hallazgos HIGH", "high_findings", "lower"),
            ("Hallazgos WARNING", "warning_findings", "lower"),
        ],
        left_metrics,
        right_metrics,
    )
    exposure_metrics = _metric_rows(
        [
            ("Dominios", "domains", "lower"),
            ("URLs", "urls", "lower"),
            ("URLs HTTP", "http_urls", "lower"),
            ("Trackers", "trackers", "lower"),
        ],
        left_metrics,
        right_metrics,
    )

    quick_kpis = _quick_kpis(left_metrics, right_metrics)
    technical_findings = _technical_findings(left_report, "left") + _technical_findings(
        right_report,
        "right",
    )

    logger.info(
        "[COMPARISON] Dashboard generado kpis=%s privacy=%s security=%s exposure=%s findings=%s",
        len(quick_kpis),
        len(privacy_metrics),
        len(security_metrics),
        len(exposure_metrics),
        len(technical_findings),
    )

    mastg = {
        "left_score": None,
        "right_score": None,
        "status": "pending",
        "label": "Índice MASTG pendiente",
    }
    header = {
        "app_name": _dashboard_app_name(prepared_a, prepared_b),
        "left": _dashboard_header_side(prepared_a, report_a),
        "right": _dashboard_header_side(prepared_b, report_b),
        # Campos legacy conservados temporalmente para clientes antiguos.
        "left_title": _dashboard_side_title(report_a),
        "right_title": _dashboard_side_title(report_b),
        "left_version": report_a.version_app.version,
        "right_version": report_b.version_app.version,
        "left_integration_model": report_a.version_app.modelo_integracion.value,
        "right_integration_model": report_b.version_app.modelo_integracion.value,
        "left_mobsf_status": report_a.version_app.estado_mobsf.value,
        "right_mobsf_status": report_b.version_app.estado_mobsf.value,
        "left_icon": build_public_artifact_url(prepared_a.application.icono),
        "right_icon": build_public_artifact_url(prepared_b.application.icono),
    }
    platform_metrics = _metric_rows(
        [
            ("targetSdk", "target_sdk", "higher"),
            ("minSdk", "min_sdk", "higher"),
        ],
        left_metrics,
        right_metrics,
    )
    verdict_cards = _verdict_cards(
        left_metrics=left_metrics,
        right_metrics=right_metrics,
        platform_metrics=platform_metrics,
        privacy_metrics=privacy_metrics,
        security_metrics=security_metrics,
        exposure_metrics=exposure_metrics,
    )
    key_findings = [_key_finding(finding) for finding in technical_findings[:20]]
    permission_diff = _permission_diff(left_report, right_report)
    technical_summary = {
        "left_report_available": report_a.mobsf_report is not None,
        "right_report_available": report_b.mobsf_report is not None,
        "left_report_size_bytes": _report_size_bytes(report_a),
        "right_report_size_bytes": _report_size_bytes(report_b),
        "raw_report_in_response": False,
    }

    return {
        "header": header,
        "mastg": mastg,
        # Alias legacy para clientes que aún esperan mastg_score.
        "mastg_score": {
            "left": None,
            "right": None,
            "status": "pending",
        },
        "executive_summary": _executive_summary(
            comparison_payload=comparison_payload,
            left_metrics=left_metrics,
            right_metrics=right_metrics,
        ),
        "verdict_cards": verdict_cards,
        "quick_kpis": verdict_cards,
        "platform_metrics": platform_metrics,
        "privacy_metrics": privacy_metrics,
        "security_metrics": security_metrics,
        "exposure_metrics": exposure_metrics,
        "key_findings": key_findings,
        "technical_findings": key_findings,
        "permission_diff": permission_diff,
        "technical_summary": technical_summary,
    }


def _dashboard_app_name(
    prepared_a: PreparedAppVersion,
    prepared_b: PreparedAppVersion,
) -> str:
    if prepared_a.application.id_app == prepared_b.application.id_app:
        return prepared_a.application.nombre
    return f"{prepared_a.application.nombre} vs {prepared_b.application.nombre}"


def _dashboard_side_title(report: VersionReport) -> str:
    model = report.version_app.modelo_integracion.value
    if model == "HEALTH_CONNECT":
        return "Health Connect"
    if model == "LEGACY":
        return "Legacy"
    return "Modelo desconocido"


def _integration_model_short(model: str) -> str:
    if model == "HEALTH_CONNECT":
        return "HC"
    if model == "LEGACY":
        return "L"
    return "?"


def _dashboard_header_side(
    prepared: PreparedAppVersion,
    report: VersionReport,
) -> dict[str, Any]:
    version = report.version_app
    model = version.modelo_integracion.value
    return {
        "label": _dashboard_side_title(report),
        "name": prepared.application.nombre,
        "app_name": prepared.application.nombre,
        "title": prepared.application.nombre,
        "app_id": version.id_app,
        "version": version.version,
        "version_code": version.version_code,
        "integration_model": model,
        "integration_model_short": _integration_model_short(model),
        "mobsf_status": version.estado_mobsf.value,
        "icon": build_public_artifact_url(prepared.application.icono),
    }


def _extract_dashboard_metrics(report_data: dict[str, Any] | None) -> dict[str, float | None]:
    if not isinstance(report_data, dict):
        return {}

    permissions = report_data.get("permissions")
    urls = _collection_items(report_data.get("urls")) if "urls" in report_data else None
    domains = _collection_items(report_data.get("domains")) if "domains" in report_data else None
    trackers = None
    if "trackers" in report_data or "trackers_info" in report_data:
        trackers = _collection_items(report_data.get("trackers")) or _collection_items(
            report_data.get("trackers_info")
        )
    findings = _technical_findings(report_data, "left")
    has_security_sections = any(
        key in report_data
        for key in [
            "certificate_analysis",
            "manifest_analysis",
            "code_analysis",
            "binary_analysis",
            "network_security",
        ]
    )

    http_urls = [value for value in (urls or []) if str(value).lower().startswith("http://")]

    return {
        "target_sdk": _first_number(
            report_data,
            ["target_sdk", "target_sdk_version", "target_sdk_version_code"],
        ),
        "min_sdk": _first_number(report_data, ["min_sdk", "min_sdk_version"]),
        "dangerous_permissions": float(_count_dangerous_permissions(permissions))
        if permissions is not None
        else None,
        "health_connect_permissions": float(_count_health_connect_permissions(permissions))
        if permissions is not None
        else None,
        "location_permissions": float(_count_permissions_matching(permissions, ["location"]))
        if permissions is not None
        else None,
        "sensor_permissions": float(_count_permissions_matching(permissions, ["sensor", "body", "activity_recognition"]))
        if permissions is not None
        else None,
        "storage_permissions": float(_count_permissions_matching(permissions, ["storage", "media", "external"]))
        if permissions is not None
        else None,
        "trackers": float(len(trackers)) if trackers is not None else None,
        "domains": float(len(domains)) if domains is not None else None,
        "urls": float(len(urls)) if urls is not None else None,
        "http_urls": float(len(http_urls)) if urls is not None else None,
        "high_findings": float(_count_findings_by_severity(findings, "high"))
        if has_security_sections
        else None,
        "warning_findings": float(_count_findings_by_severity(findings, "warning"))
        if has_security_sections
        else None,
        "trackers_examples": _string_examples(trackers or []),
        "domains_examples": _string_examples(domains or []),
        "urls_examples": _string_examples(urls or []),
        "http_urls_examples": _string_examples(http_urls),
        "permissions_examples": _string_examples(_permission_names(permissions)),
        "findings_examples": [finding["title"] for finding in findings[:20]],
        "total_trackers": len(trackers or []),
        "total_domains": len(domains or []),
        "total_urls": len(urls or []),
        "total_http_urls": len(http_urls),
        "total_permissions": _collection_count(permissions),
        "total_findings": len(findings),
    }



def _verdict_cards(
    left_metrics: dict[str, float | None],
    right_metrics: dict[str, float | None],
    platform_metrics: list[dict[str, Any]],
    privacy_metrics: list[dict[str, Any]],
    security_metrics: list[dict[str, Any]],
    exposure_metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cards = [
        _verdict_card(
            title="Plataforma Android",
            metrics=platform_metrics,
            fallback_summary="Compara targetSdk/minSdk y adaptación a Android moderno.",
        ),
        _verdict_card(
            title="Permisos sensibles",
            metrics=privacy_metrics,
            fallback_summary=(
                "Health Connect puede declarar más permisos, pero suelen ser más granulares "
                "para datos de salud."
            ),
            force_review=True,
        ),
        _verdict_card(
            title="Riesgos MobSF",
            metrics=security_metrics,
            fallback_summary="Resume hallazgos técnicos HIGH/WARNING detectados por MobSF.",
        ),
        _verdict_card(
            title="Exposición externa",
            metrics=exposure_metrics,
            fallback_summary="Compara trackers, dominios y URLs externas detectadas.",
        ),
        {
            "title": "Comunicaciones",
            "winner": _winner_for_values(
                left_metrics.get("http_urls"),
                right_metrics.get("http_urls"),
                preferred="lower",
            ),
            "status": "warning"
            if left_metrics.get("http_urls") or right_metrics.get("http_urls")
            else "neutral",
            "summary": "Revisa URLs HTTP y posibles comunicaciones sin cifrado.",
        },
        {
            "title": "MASTG",
            "winner": "pending",
            "status": "neutral",
            "summary": "El índice MASTG final está pendiente y no se infiere desde MobSF.",
        },
    ]
    return cards


def _verdict_card(
    title: str,
    metrics: list[dict[str, Any]],
    fallback_summary: str,
    force_review: bool = False,
) -> dict[str, Any]:
    if force_review or not metrics:
        return {
            "title": title,
            "winner": "review",
            "status": "warning" if force_review else "neutral",
            "summary": fallback_summary,
        }

    left_wins = 0
    right_wins = 0
    for metric in metrics:
        winner = _winner_for_values(
            metric.get("left_value"),
            metric.get("right_value"),
            metric.get("preferred"),
        )
        if winner == "left":
            left_wins += 1
        elif winner == "right":
            right_wins += 1

    if left_wins > right_wins:
        winner = "left"
        status = "positive"
    elif right_wins > left_wins:
        winner = "right"
        status = "warning"
    else:
        winner = "tie" if left_wins or right_wins else "review"
        status = "neutral" if winner == "tie" else "warning"

    return {
        "title": title,
        "winner": winner,
        "status": status,
        "summary": fallback_summary,
    }


def _winner_for_values(
    left_value: Any,
    right_value: Any,
    preferred: str | None,
) -> str:
    left_number = _number_or_none(left_value)
    right_number = _number_or_none(right_value)
    if left_number is None or right_number is None or left_number == right_number:
        return "tie" if left_number is not None and right_number is not None else "review"
    if preferred == "higher":
        return "left" if left_number > right_number else "right"
    if preferred == "lower":
        return "left" if left_number < right_number else "right"
    return "review"


def _quick_kpis(
    left_metrics: dict[str, float | None],
    right_metrics: dict[str, float | None],
) -> list[dict[str, Any]]:
    rows = []
    target_sdk = _quick_kpi(
        title="Plataforma Android",
        left_value=left_metrics.get("target_sdk"),
        right_value=right_metrics.get("target_sdk"),
        label_suffix="targetSdk",
        higher_is_better=True,
    )
    if target_sdk:
        rows.append(target_sdk)

    dangerous_permissions = _quick_kpi(
        title="Permisos sensibles",
        left_value=left_metrics.get("dangerous_permissions"),
        right_value=right_metrics.get("dangerous_permissions"),
        label_suffix="dangerous",
        higher_is_better=False,
        force_review=True,
    )
    if dangerous_permissions:
        rows.append(dangerous_permissions)

    trackers = _quick_kpi(
        title="Trackers detectados",
        left_value=left_metrics.get("trackers"),
        right_value=right_metrics.get("trackers"),
        label_suffix="trackers",
        higher_is_better=False,
    )
    if trackers:
        rows.append(trackers)

    return rows


def _quick_kpi(
    title: str,
    left_value: float | None,
    right_value: float | None,
    label_suffix: str,
    higher_is_better: bool,
    force_review: bool = False,
) -> dict[str, Any] | None:
    if left_value is None and right_value is None:
        return None

    winner = "review"
    level = "warning"
    if not force_review and left_value is not None and right_value is not None and left_value != right_value:
        left_wins = left_value > right_value if higher_is_better else left_value < right_value
        winner = "left" if left_wins else "right"
        level = "positive"

    return {
        "title": title,
        "left_label": _metric_label(left_value, label_suffix),
        "right_label": _metric_label(right_value, label_suffix),
        "left_value": left_value,
        "right_value": right_value,
        "winner": winner,
        "level": level,
    }



def _preferred_for_metric(key: str) -> str:
    if key in {"target_sdk", "min_sdk"}:
        return "higher"
    if key in {
        "dangerous_permissions",
        "location_permissions",
        "storage_permissions",
        "trackers",
        "domains",
        "urls",
        "http_urls",
        "high_findings",
        "warning_findings",
    }:
        return "lower"
    return "context"


def _plain_metric_label(value: Any) -> str:
    number = _number_or_none(value)
    if number is None:
        return "N/D"
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _metric_rows(
    definitions: list[tuple[str, str] | tuple[str, str, str]],
    left_metrics: dict[str, float | None],
    right_metrics: dict[str, float | None],
) -> list[dict[str, Any]]:
    rows = []
    for definition in definitions:
        label, key = definition[0], definition[1]
        preferred = definition[2] if len(definition) > 2 else _preferred_for_metric(key)
        left_value = left_metrics.get(key)
        right_value = right_metrics.get(key)
        if left_value is None and right_value is None:
            continue
        row = {
            "label": label,
            "left_value": left_value,
            "right_value": right_value,
            "left_label": _plain_metric_label(left_value),
            "right_label": _plain_metric_label(right_value),
            "preferred": preferred,
        }
        left_examples = left_metrics.get(f"{key}_examples")
        right_examples = right_metrics.get(f"{key}_examples")
        if left_examples:
            row["left_examples"] = left_examples
        if right_examples:
            row["right_examples"] = right_examples
        total_left = left_metrics.get(f"total_{key}")
        total_right = right_metrics.get(f"total_{key}")
        if total_left is not None:
            row["left_total"] = total_left
        if total_right is not None:
            row["right_total"] = total_right
        if (left_examples and total_left and total_left > len(left_examples)) or (
            right_examples and total_right and total_right > len(right_examples)
        ):
            row["examples_truncated"] = True
        rows.append(row)
    return rows


def _executive_summary(
    comparison_payload: dict[str, Any],
    left_metrics: dict[str, float | None],
    right_metrics: dict[str, float | None],
) -> list[str]:
    summary = comparison_payload.get("summary", {})
    sentences = []

    if summary.get("left_model") != summary.get("right_model"):
        sentences.append(
            "Las versiones comparadas usan modelos de integración distintos, por lo que conviene revisar los cambios funcionales y de privacidad."
        )

    if _number_or_none(left_metrics.get("target_sdk")) and _number_or_none(right_metrics.get("target_sdk")):
        if float(left_metrics["target_sdk"]) != float(right_metrics["target_sdk"]):
            sentences.append(
                "La comparativa detecta diferencias en la plataforma Android objetivo declarada por cada versión."
            )

    if _number_or_none(left_metrics.get("trackers")) and _number_or_none(right_metrics.get("trackers")):
        if float(left_metrics["trackers"]) != float(right_metrics["trackers"]):
            sentences.append(
                "Los informes MobSF muestran diferencias en la exposición a trackers entre ambas versiones."
            )

    if _number_or_none(left_metrics.get("high_findings")) or _number_or_none(right_metrics.get("high_findings")):
        sentences.append(
            "MobSF ha identificado hallazgos técnicos de seguridad que requieren revisión antes de sacar conclusiones finales."
        )

    if not sentences:
        sentences.append(
            "La comparativa inicial se ha generado con la información disponible en los informes MobSF."
        )

    return sentences[:4]


def _first_number(data: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = data.get(key)
        number = _number_or_none(value)
        if number is not None:
            return number
    return None


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _metric_label(value: float | None, suffix: str) -> str:
    if value is None:
        return "No disponible"
    if float(value).is_integer():
        return f"{int(value)} {suffix}"
    return f"{value:.1f} {suffix}"


def _collection_items(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values()) if value else []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _count_dangerous_permissions(value: Any) -> int:
    if isinstance(value, dict):
        total = 0
        for permission, details in value.items():
            haystack = f"{permission} {details}".lower()
            if "dangerous" in haystack:
                total += 1
        return total
    if isinstance(value, list):
        return sum(1 for item in value if "dangerous" in str(item).lower())
    return 0


def _count_health_connect_permissions(value: Any) -> int:
    if isinstance(value, dict):
        permission_names = value.keys()
    elif isinstance(value, list):
        permission_names = value
    else:
        return 0

    return sum(
        1
        for permission in permission_names
        if "health" in str(permission).lower()
    )



def _permission_diff(
    left_report: dict[str, Any] | None,
    right_report: dict[str, Any] | None,
) -> dict[str, list[str]]:
    left_permissions = set(_permission_names(left_report.get("permissions") if isinstance(left_report, dict) else None))
    right_permissions = set(_permission_names(right_report.get("permissions") if isinstance(right_report, dict) else None))
    return {
        "added_in_left": sorted(left_permissions - right_permissions)[:50],
        "removed_in_left": sorted(right_permissions - left_permissions)[:50],
        "health_connect_permissions": sorted(
            permission for permission in left_permissions if "health" in str(permission).lower()
        )[:50],
    }


def _key_finding(finding: dict[str, Any]) -> dict[str, Any]:
    title = finding.get("title") or "Hallazgo técnico"
    summary = finding.get("description") or finding.get("detail") or title
    return {
        "title": title,
        "severity": finding.get("severity"),
        "category": _finding_category(title),
        "affected_side": finding.get("affected_side"),
        "summary": str(summary)[:500],
        "mastg_relation": _mastg_relation_for_finding(title),
        "relation_type": "inferred",
        "masvs": finding.get("masvs"),
        "cwe": finding.get("cwe"),
    }


def _finding_category(title: Any) -> str:
    text = str(title).lower()
    if "clear" in text or "traffic" in text or "http" in text or "network" in text:
        return "Comunicaciones"
    if "backup" in text or "storage" in text or "external" in text:
        return "Almacenamiento"
    if "webview" in text:
        return "WebView"
    if "crypto" in text or "ssl" in text or "tls" in text:
        return "Criptografía"
    if "log" in text:
        return "Logging"
    if "permission" in text:
        return "Permisos"
    return "Seguridad"


def _mastg_relation_for_finding(title: Any) -> str | None:
    text = str(title).lower()
    if "clear" in text or "traffic" in text or "http" in text:
        return "MASTG-TEST-0235"
    if "backup" in text:
        return "MASTG-TEST-0216"
    if "webview" in text:
        return "MASTG-TEST-0252"
    if "crypto" in text or "ssl" in text or "tls" in text:
        return "MASTG-TEST-0221"
    return None


def _count_permissions_matching(value: Any, needles: list[str]) -> int:
    return sum(
        1
        for permission in _permission_names(value)
        if any(needle in str(permission).lower() for needle in needles)
    )


def _technical_findings(
    report_data: dict[str, Any] | None,
    affected_side: str,
) -> list[dict[str, Any]]:
    if not isinstance(report_data, dict):
        return []

    findings: list[dict[str, Any]] = []
    for section_key in [
        "certificate_analysis",
        "manifest_analysis",
        "code_analysis",
        "binary_analysis",
        "network_security",
    ]:
        section = report_data.get(section_key)
        for title, details in _iter_finding_items(section):
            severity = _finding_severity(details)
            if not severity:
                continue
            findings.append(
                {
                    "title": _clean_finding_title(title),
                    "severity": severity.upper(),
                    "affected_side": affected_side,
                    "description": _finding_description(details),
                    "detail": _finding_detail(details),
                    "masvs": _finding_optional(details, ["masvs", "owasp-mobile", "masvs_control"]),
                    "cwe": _finding_optional(details, ["cwe", "cwe_id"]),
                }
            )
    return findings


def _iter_finding_items(section: Any) -> list[tuple[str, Any]]:
    if isinstance(section, dict):
        items: list[tuple[str, Any]] = []
        for key, value in section.items():
            if isinstance(value, dict) and any(
                field in value for field in ["severity", "cvss", "metadata", "description"]
            ):
                items.append((str(key), value))
            elif isinstance(value, dict):
                items.extend(_iter_finding_items(value))
        return items
    if isinstance(section, list):
        return [(str(item.get("title", item.get("name", "Hallazgo"))), item) for item in section if isinstance(item, dict)]
    return []


def _finding_severity(details: Any) -> str | None:
    if not isinstance(details, dict):
        return None
    severity = details.get("severity") or details.get("level")
    if severity:
        return str(severity)
    metadata = details.get("metadata")
    if isinstance(metadata, dict) and metadata.get("severity"):
        return str(metadata["severity"])
    return None


def _finding_description(details: Any) -> str | None:
    if not isinstance(details, dict):
        return None
    value = details.get("description") or details.get("desc") or details.get("title")
    return str(value)[:1000] if value else None


def _finding_detail(details: Any) -> str | None:
    if not isinstance(details, dict):
        return None
    value = details.get("detail") or details.get("info") or details.get("files")
    if value is None:
        value = details.get("metadata")
    return str(value)[:1500] if value is not None else None


def _finding_optional(details: Any, keys: list[str]) -> str | None:
    if not isinstance(details, dict):
        return None
    for key in keys:
        value = details.get(key)
        if value:
            return str(value)[:300]
    metadata = details.get("metadata")
    if isinstance(metadata, dict):
        for key in keys:
            value = metadata.get(key)
            if value:
                return str(value)[:300]
    return None


def _clean_finding_title(value: str) -> str:
    return value.replace("_", " ").strip().title() or "Hallazgo técnico"


def _count_findings_by_severity(findings: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for finding in findings if finding.get("severity", "").lower() == severity.lower())


def _build_technical_summary(
    report_a: VersionReport,
    report_b: VersionReport,
) -> dict[str, Any]:
    return {
        "left_report_available": report_a.mobsf_report is not None,
        "right_report_available": report_b.mobsf_report is not None,
        "left_report_size_bytes": _report_size_bytes(report_a),
        "right_report_size_bytes": _report_size_bytes(report_b),
        "left_report_keys": _report_keys(report_a),
        "right_report_keys": _report_keys(report_b),
        "left_report_path": report_a.version_app.ruta_informe_mobsf,
        "right_report_path": report_b.version_app.ruta_informe_mobsf,
    }


def _report_size_bytes(report: VersionReport) -> int | None:
    report_path = report.version_app.ruta_informe_mobsf
    if not report_path:
        return None
    try:
        return Path(report_path).stat().st_size
    except OSError:
        return None


def _report_keys(report: VersionReport) -> list[str]:
    json_report = report.mobsf_report.json_report if report.mobsf_report else None
    if not isinstance(json_report, dict):
        return []
    return sorted(json_report.keys())[:50]


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value[:300]
    return str(value)[:300]


def _string_examples(values: list[Any], limit: int = 20) -> list[str]:
    return [str(value)[:500] for value in values[:limit]]


def _collection_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return 0


def _permission_names(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.keys())
    if isinstance(value, list):
        return value
    return []

def _save_temporary_comparison_payload(
    payload: dict[str, Any],
    dashboard_payload: dict[str, Any],
    technical_summary: dict[str, Any],
) -> str:
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

    artifact_payload = {
        "comparison": payload,
        "dashboard": dashboard_payload,
        "technical_summary": technical_summary,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(artifact_payload, file, ensure_ascii=False, indent=2, default=str)

    return str(output_path)


def _safe_filename_part(value: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "unknown").strip())
    return cleaned[:80] or "unknown"

def _evaluate_mastg_for_comparison(
    db: Session,
    report_a: VersionReport,
    report_b: VersionReport,
    index_id: str,
    messages: list[str],
) -> dict[str, Any]:
    service = MastgEvaluationService(db)

    left_result = service.evaluate_version(
        index_id=index_id,
        id_app=report_a.version_app.id_app,
        version=report_a.version_app.version,
    )
    messages.append(
        "[MASTG] Evaluación completada para "
        f"{report_a.version_app.id_app}:{report_a.version_app.version} "
        f"con índice {index_id}."
    )

    right_result = service.evaluate_version(
        index_id=index_id,
        id_app=report_b.version_app.id_app,
        version=report_b.version_app.version,
    )
    messages.append(
        "[MASTG] Evaluación completada para "
        f"{report_b.version_app.id_app}:{report_b.version_app.version} "
        f"con índice {index_id}."
    )

    return {
        "index_id": index_id,
        "label": left_result.get("index", {}).get("nombre") or index_id,
        "left": left_result,
        "right": right_result,
        "tests": _merge_mastg_test_results(
            left_result.get("results", []),
            right_result.get("results", []),
        ),
    }


def _apply_mastg_to_dashboard(
    dashboard_payload: dict[str, Any],
    mastg_payload: dict[str, Any],
) -> None:
    left_score = _mastg_score_value(mastg_payload.get("left"))
    right_score = _mastg_score_value(mastg_payload.get("right"))
    left_coverage = _mastg_coverage_value(mastg_payload.get("left"))
    right_coverage = _mastg_coverage_value(mastg_payload.get("right"))

    label = mastg_payload.get("label") or "Índice MASTG"
    index_id = mastg_payload.get("index_id")

    dashboard_payload["mastg"] = {
        "left_score": left_score,
        "right_score": right_score,
        "left_coverage": left_coverage,
        "right_coverage": right_coverage,
        "status": "completed",
        "label": label,
        "index_id": index_id,
        "tests": mastg_payload.get("tests", []),
        "left_summary": _mastg_status_summary(mastg_payload.get("left")),
        "right_summary": _mastg_status_summary(mastg_payload.get("right")),
    }

    # Alias legacy usado por la pantalla Kotlin actual.
    dashboard_payload["mastg_score"] = {
        "left": left_score,
        "right": right_score,
        "left_coverage": left_coverage,
        "right_coverage": right_coverage,
        "status": "completed",
        "label": label,
        "index_id": index_id,
    }


def _mastg_score_value(result: Any) -> float | None:
    if not isinstance(result, dict):
        return None

    score = result.get("score", {}).get("score")

    if score is None:
        return None

    return float(score)


def _mastg_coverage_value(result: Any) -> float | None:
    if not isinstance(result, dict):
        return None

    coverage = result.get("score", {}).get("coverage")

    if coverage is None:
        return None

    return float(coverage)


def _mastg_status_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}

    score = result.get("score", {})

    if not isinstance(score, dict):
        return {}

    return {
        "score": score.get("score"),
        "score_percent": score.get("score_percent"),
        "coverage": score.get("coverage"),
        "coverage_percent": score.get("coverage_percent"),
        "total_tests": score.get("total_tests"),
        "scorable_tests": score.get("scorable_tests"),
        "status_summary": score.get("status_summary", {}),
    }


def _merge_mastg_test_results(
    left_results: list[dict[str, Any]],
    right_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for item in left_results:
        id_mastg = item.get("id_mastg")
        if not id_mastg:
            continue

        by_id.setdefault(
            id_mastg,
            {
                "id": id_mastg,
                "title": item.get("nombre") or id_mastg,
                "relation": item.get("tipo_relacion") or item.get("origen"),
                "category": item.get("categoria_masvs"),
                "origin": item.get("origen"),
                "left_status": None,
                "right_status": None,
                "left_summary": None,
                "right_summary": None,
                "left_recommendation": None,
                "right_recommendation": None,
                "left_result_json": None,
                "right_result_json": None,
            },
        )

        by_id[id_mastg].update(
            {
                "left_status": _normalize_mastg_status_for_android(item.get("resultado")),
                "left_summary": item.get("summary"),
                "left_recommendation": item.get("recommendation"),
                "left_result_json": item.get("ruta_resultado_json"),
            }
        )

    for item in right_results:
        id_mastg = item.get("id_mastg")
        if not id_mastg:
            continue

        by_id.setdefault(
            id_mastg,
            {
                "id": id_mastg,
                "title": item.get("nombre") or id_mastg,
                "relation": item.get("tipo_relacion") or item.get("origen"),
                "category": item.get("categoria_masvs"),
                "origin": item.get("origen"),
                "left_status": None,
                "right_status": None,
                "left_summary": None,
                "right_summary": None,
                "left_recommendation": None,
                "right_recommendation": None,
                "left_result_json": None,
                "right_result_json": None,
            },
        )

        by_id[id_mastg].update(
            {
                "right_status": _normalize_mastg_status_for_android(item.get("resultado")),
                "right_summary": item.get("summary"),
                "right_recommendation": item.get("recommendation"),
                "right_result_json": item.get("ruta_resultado_json"),
            }
        )

    return [
        by_id[id_mastg]
        for id_mastg in sorted(by_id)
    ]


def _normalize_mastg_status_for_android(value: Any) -> str:
    normalized = str(value or "NOT_EVALUABLE").upper()

    if normalized in {"PASS", "FAIL", "REVIEW", "ERROR", "NOT_EVALUABLE"}:
        return normalized

    if normalized in {"NOT_EXECUTED", "NOT_APPLICABLE"}:
        return "NOT_EVALUABLE"

    return "NOT_EVALUABLE"