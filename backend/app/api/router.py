from fastapi import APIRouter

from app.api.routes import apps, comparisons, mastg, system


api_router = APIRouter()

api_router.include_router(apps.router)
api_router.include_router(comparisons.router)
api_router.include_router(mastg.router)
api_router.include_router(system.router)
