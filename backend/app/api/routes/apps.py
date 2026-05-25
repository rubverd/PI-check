import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.apps import AppSearchResponse
from app.services.google_play_service import (
    GooglePlaySearchError,
    search_google_play_apps,
)

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