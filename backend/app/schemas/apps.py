from typing import Literal, Optional

from pydantic import BaseModel


IntegrationModelApi = Literal["legacy", "health_connect", "unknown"]
MobsfStatusApi = Literal["not_analyzed", "pending", "success", "error"]


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


class RegisteredAppItem(BaseModel):
    app_id: str
    name: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    category: str = ""

    version: str
    version_code: Optional[int] = None
    version_date: Optional[str] = None

    integration_model: IntegrationModelApi
    mobsf_status: MobsfStatusApi
    mobsf_report_available: bool = False


class RegisteredAppsResponse(BaseModel):
    count: int
    results: list[RegisteredAppItem]


class AnalyzedAppItem(BaseModel):
    app_id: str
    name: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    version: str
    category: str = ""
    analysis_date: str = ""
    integration_model: IntegrationModelApi
    mobsf_status: MobsfStatusApi = "success"
    mobsf_report_available: bool = True


class AnalyzedAppsResponse(BaseModel):
    count: int
    results: list[AnalyzedAppItem]