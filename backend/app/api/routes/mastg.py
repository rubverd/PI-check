from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.services.mastg.mastg_evaluation_service import (
    MastgEvaluationService,
)
from app.application.services.comparison_service import (
    _mastg_coverage_value,
    _mastg_score_value,
    _mastg_status_summary,
    _merge_mastg_test_results,
)
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger("pi-check")

router = APIRouter(
    prefix="/api/mastg",
    tags=["mastg"],
)


class MastgEvaluateVersionRequest(BaseModel):
    id_app: str = Field(..., description="Package name de la aplicación registrada.")
    version: str = Field(..., description="Versión registrada en version_app.")
    index_id: str = Field(
        default="picheck_mhealth_v1",
        description="Índice de privacidad MASTG/PI-check a ejecutar.",
    )


class MastgComparisonSideRequest(BaseModel):
    id_app: str
    version: str


class MastgEvaluateComparisonRequest(BaseModel):
    left: MastgComparisonSideRequest
    right: MastgComparisonSideRequest
    index_id: str = "picheck_mhealth_v1"


@router.get("/indexes")
def list_indexes(db: Session = Depends(get_db_session)) -> dict[str, Any]:
    rows = db.execute(text("""
            SELECT
                i.id_indice,
                i.nombre,
                i.descripcion,
                i.ruta_del_script,
                COUNT(fp.id_mastg) AS total_pruebas
            FROM indice_privacidad i
            LEFT JOIN formar_parte fp ON fp.id_indice = i.id_indice
            GROUP BY
                i.id_indice,
                i.nombre,
                i.descripcion,
                i.ruta_del_script
            ORDER BY i.id_indice
            """)).mappings().all()

    results = [dict(row) for row in rows]

    return {
        "count": len(results),
        "results": results,
    }


@router.get("/indexes/{id_indice}")
def get_index_detail(
    id_indice: str,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    index = (
        db.execute(
            text("""
            SELECT
                id_indice,
                nombre,
                descripcion,
                ruta_del_script
            FROM indice_privacidad
            WHERE id_indice = :id_indice
            """),
            {"id_indice": id_indice},
        )
        .mappings()
        .first()
    )

    if index is None:
        raise HTTPException(
            status_code=404,
            detail=f"No existe el índice de privacidad: {id_indice}",
        )

    tests = (
        db.execute(
            text("""
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
            WHERE fp.id_indice = :id_indice
            ORDER BY pm.id_mastg
            """),
            {"id_indice": id_indice},
        )
        .mappings()
        .all()
    )

    test_results = [dict(row) for row in tests]

    return {
        "index": dict(index),
        "total_tests": len(test_results),
        "tests": test_results,
    }


@router.post("/evaluate-comparison")
def evaluate_comparison(
    request: MastgEvaluateComparisonRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    service = MastgEvaluationService(db)

    try:
        left_result = service.ensure_version_results_for_index(
            index_id=request.index_id,
            id_app=request.left.id_app,
            version=request.left.version,
        )
        right_result = service.ensure_version_results_for_index(
            index_id=request.index_id,
            id_app=request.right.id_app,
            version=request.right.version,
        )
        available_indexes = service.available_index_options()
        label = left_result.get("index", {}).get("nombre") or request.index_id
        mastg = {
            "left_score": _mastg_score_value(left_result),
            "right_score": _mastg_score_value(right_result),
            "left_coverage": _mastg_coverage_value(left_result),
            "right_coverage": _mastg_coverage_value(right_result),
            "status": "completed",
            "label": label,
            "index_id": request.index_id,
            "available_indexes": available_indexes,
            "tests": _merge_mastg_test_results(
                left_result.get("results", []),
                right_result.get("results", []),
            ),
            "left_summary": _mastg_status_summary(left_result),
            "right_summary": _mastg_status_summary(right_result),
        }
        mastg_score = {
            "left": mastg["left_score"],
            "right": mastg["right_score"],
            "left_coverage": mastg["left_coverage"],
            "right_coverage": mastg["right_coverage"],
            "status": "completed",
            "label": label,
            "index_id": request.index_id,
        }
        return {
            "status": "completed",
            "index_id": request.index_id,
            "label": label,
            "mastg": mastg,
            "mastg_score": mastg_score,
        }

    except ValueError as exc:
        db.rollback()
        logger.exception("Error controlado ejecutando comparación MASTG")
        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:
        db.rollback()
        logger.exception("Error inesperado ejecutando comparación MASTG")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado ejecutando comparación MASTG: {exc}",
        )


@router.post("/evaluate-version")
def evaluate_version(
    request: MastgEvaluateVersionRequest,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    service = MastgEvaluationService(db)

    try:
        result = service.ensure_version_results_for_index(
            index_id=request.index_id,
            id_app=request.id_app,
            version=request.version,
        )

        return {
            "status": "completed",
            "message": "Evaluación MASTG disponible correctamente.",
            **result,
        }

    except ValueError as exc:
        db.rollback()
        logger.exception("Error controlado ejecutando evaluación MASTG")
        raise HTTPException(status_code=404, detail=str(exc))

    except Exception as exc:
        db.rollback()
        logger.exception("Error inesperado ejecutando evaluación MASTG")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado ejecutando evaluación MASTG: {exc}",
        )
