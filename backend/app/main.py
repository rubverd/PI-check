from datetime import datetime, timezone
import logging

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.api.router import api_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("pi-check")


app = FastAPI(
    title="PI-check API",
    description="Backend preliminar para la herramienta PI-check",
    version="0.3.0",
)


class HistoryRequest(BaseModel):
    source: str
    message: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    content_type = request.headers.get("content-type", "")
    content_length = request.headers.get("content-length")

    logger.info("Petición recibida")
    logger.info("Método: %s", request.method)
    logger.info("Ruta: %s", request.url.path)
    logger.info("Content-Type: %s", content_type or "<sin content-type>")
    logger.info("Content-Length: %s", content_length or "<desconocido>")

    if _should_log_request_body(content_type):
        body = await request.body()
        _replay_request_body(request, body)
        if body:
            logger.info(
                "Cuerpo de la petición: %s",
                body.decode("utf-8", errors="replace"),
            )
    else:
        logger.info("Cuerpo de la petición omitido. content-type=%s", content_type)

    response = await call_next(request)

    logger.info("Código de respuesta: %s", response.status_code)

    return response


def _replay_request_body(request: Request, body: bytes) -> None:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive


def _should_log_request_body(content_type: str) -> bool:
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()

    if not media_type:
        return False

    if media_type in {"multipart/form-data", "application/octet-stream"}:
        return False

    return (
        media_type == "application/json"
        or media_type.endswith("+json")
        or media_type.startswith("text/")
        or media_type == "application/x-www-form-urlencoded"
    )


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "app": "PI-check API",
        "status": "running",
        "version": "0.3.0",
    }


@app.get("/health")
def health_check():
    logger.info("Health check recibido desde cliente")

    return {
        "status": "ok",
        "service": "PI-check backend",
        "version": "0.3.0",
    }


@app.post("/api/history/ping")
def history_ping(request: HistoryRequest):
    logger.info("Mensaje recibido desde la app móvil")
    logger.info("Origen: %s", request.source)
    logger.info("Mensaje: %s", request.message)

    response = {
        "received": True,
        "source": request.source,
        "message": request.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("Respuesta enviada a la app: %s", response)

    return response
