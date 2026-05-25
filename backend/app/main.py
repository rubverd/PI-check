from datetime import datetime, timezone
import logging

from fastapi import FastAPI, Request
from pydantic import BaseModel


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("pi-check")


app = FastAPI(
    title="PI-check API",
    description="Backend preliminar para la herramienta PI-check",
    version="0.1.0",
)


class HistoryRequest(BaseModel):
    source: str
    message: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()

    logger.info("Petición recibida")
    logger.info("Método: %s", request.method)
    logger.info("Ruta: %s", request.url.path)

    if body:
        logger.info("Cuerpo de la petición: %s", body.decode("utf-8"))

    response = await call_next(request)

    logger.info("Código de respuesta: %s", response.status_code)

    return response


@app.get("/")
def root():
    return {
        "app": "PI-check API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    logger.info("Health check recibido desde cliente")

    return {
        "status": "ok",
        "service": "PI-check backend",
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