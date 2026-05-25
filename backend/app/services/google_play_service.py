import logging

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

        apps.append(
            AppSearchItem(
                app_id=app_id,
                title=item.get("title") or "Sin título",
                developer=item.get("developer"),
                icon=item.get("icon"),
                score=item.get("score"),
                genre=item.get("genre"),
                free=item.get("free"),
                url=item.get("url")
                or f"https://play.google.com/store/apps/details?id={app_id}",
            )
        )

    logger.info("Aplicaciones válidas encontradas: %s", len(apps))

    return apps