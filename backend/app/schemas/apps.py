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


class RegisteredAppVersionItem(BaseModel):
    version: str
    version_code: Optional[int] = None
    version_date: Optional[str] = None
    integration_model: IntegrationModelApi
    integration_model_short: str
    mobsf_status: MobsfStatusApi
    mobsf_report_available: bool = False
    apk_sha256: Optional[str] = None
    ruta_apk: Optional[str] = None


class RegisteredAppItem(BaseModel):
    app_id: str
    name: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    category: str = ""
    versions: list[RegisteredAppVersionItem] = []

    # Campos derivados de la versión más reciente para mantener compatibilidad
    # razonable con clientes antiguos que todavía esperan una única versión.
    version: Optional[str] = None
    version_code: Optional[int] = None
    version_date: Optional[str] = None
    integration_model: Optional[IntegrationModelApi] = None
    integration_model_short: Optional[str] = None
    mobsf_status: Optional[MobsfStatusApi] = None
    mobsf_report_available: bool = False
    apk_sha256: Optional[str] = None
    ruta_apk: Optional[str] = None


class RegisteredAppsResponse(BaseModel):
    count: int
    results: list[RegisteredAppItem]


class RegisterLocalApkRequest(BaseModel):
    apk_path: str
    title: Optional[str] = None
    developer: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    run_mobsf: bool = False
    source_label: Optional[str] = None
    version_date: Optional[str] = None


class RegisterLocalApkResponse(BaseModel):
    app: RegisteredAppItem
    version: RegisteredAppVersionItem
    run_mobsf: bool
    mobsf_report_available: bool = False
    already_registered: bool = False
    messages: list[str]


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
