import logging

from fastapi import APIRouter, HTTPException, Query

from app.infrastructure.external.google_play_client import (
    GooglePlaySearchError,
    search_google_play_apps,
)
from app.schemas.apps import AnalyzedAppsResponse, AppSearchResponse


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

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        )

    except Exception as exc:
        logger.exception("Error inesperado buscando aplicaciones")

        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado buscando aplicaciones: {exc}",
        )


@router.get("/analyzed", response_model=AnalyzedAppsResponse)
def get_analyzed_apps():
    # La base de datos de aplicaciones analizadas todavía no está implementada.
    # Se mantiene el endpoint para que el cliente Android use el flujo real de API
    # y reciba una respuesta estable aunque la lista esté vacía.
    return AnalyzedAppsResponse(
        count=0,
        results=[],
    )