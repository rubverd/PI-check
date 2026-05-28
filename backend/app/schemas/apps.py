from typing import Literal, Optional

from pydantic import BaseModel


class AppSearchItem(BaseModel):
    app_id: str
    title: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    score: Optional[float] = None
    genre: Optional[str] = None
    free: Optional[bool] = None
    url: Optional[str] = None
    version: Optional[str] = None
    version_date: Optional[str] = None


class AppSearchResponse(BaseModel):
    query: str
    count: int
    results: list[AppSearchItem]


class AnalyzedAppItem(BaseModel):
    app_id: str
    name: str
    version: str
    category: str
    analysis_date: str
    integration_model: Literal["legacy", "health_connect"]


class AnalyzedAppsResponse(BaseModel):
    count: int
    results: list[AnalyzedAppItem]
