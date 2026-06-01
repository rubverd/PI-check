from datetime import datetime, timezone
import logging
from typing import Any

from google_play_scraper import app as get_google_play_app_details
from google_play_scraper import search

from app.schemas.apps import AppSearchItem

logger = logging.getLogger("pi-check")


class GooglePlaySearchError(Exception):
    """Error controlado durante la búsqueda de aplicaciones en Google Play."""


def search_google_play_apps(
    query: str,
    limit: int = 10,
    lang: str = "es",
    country: str = "es",
) -> list[AppSearchItem]:
    logger.info(
        "Buscando aplicaciones en Google Play. query=%s, limit=%s, lang=%s, country=%s",
        query,
        limit,
        lang,
        country,
    )

    attempts = [
        (lang, country),
        ("en", "us"),
    ]

    raw_results = None
    selected_lang = lang
    selected_country = country
    last_error: Exception | None = None

    for attempt_lang, attempt_country in attempts:
        try:
            logger.info(
                "Intentando búsqueda con lang=%s, country=%s",
                attempt_lang,
                attempt_country,
            )

            raw_results = search(
                query,
                lang=attempt_lang,
                country=attempt_country,
                n_hits=limit,
            )

            if raw_results:
                selected_lang = attempt_lang
                selected_country = attempt_country
                break

        except Exception as exc:
            last_error = exc
            logger.warning(
                "Fallo buscando apps con lang=%s, country=%s: %s",
                attempt_lang,
                attempt_country,
                exc,
            )

    if raw_results is None:
        logger.exception("No se pudo obtener respuesta válida de Google Play")
        raise GooglePlaySearchError(
            "No se pudo obtener una respuesta válida desde Google Play Scraper."
        ) from last_error

    apps: list[AppSearchItem] = []

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        app_id = item.get("appId")

        if not app_id:
            continue

        details = _get_app_details(
            app_id=app_id,
            lang=selected_lang,
            country=selected_country,
        )

        apps.append(
            AppSearchItem(
                app_id=app_id,
                title=item.get("title") or details.get("title") or "Sin título",
                developer=item.get("developer") or details.get("developer"),
                icon=item.get("icon") or details.get("icon"),
                score=item.get("score") or details.get("score"),
                genre=item.get("genre") or details.get("genre"),
                free=item.get("free") if item.get("free") is not None else details.get("free"),
                url=item.get("url")
                or details.get("url")
                or f"https://play.google.com/store/apps/details?id={app_id}",
                version=details.get("version") or item.get("version"),
                version_date=_format_version_date(
                    details.get("updated") or item.get("updated") or details.get("released")
                ),
            )
        )

    logger.info("Aplicaciones válidas encontradas: %s", len(apps))

    return apps


def _get_app_details(app_id: str, lang: str, country: str) -> dict[str, Any]:
    try:
        details = get_google_play_app_details(
            app_id,
            lang=lang,
            country=country,
        )

        if isinstance(details, dict):
            return details
    except Exception as exc:
        logger.warning(
            "No se pudo obtener detalle de Google Play para app_id=%s: %s",
            app_id,
            exc,
        )

    return {}


def _format_version_date(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()

    return str(value)
