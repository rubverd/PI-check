from typing import Any, Optional

from pydantic import BaseModel, Field


class SelectedAppMetadata(BaseModel):
    app_id: str
    title: str
    developer: Optional[str] = None
    icon: Optional[str] = None
    score: Optional[float] = None
    genre: Optional[str] = None
    url: Optional[str] = None
    version: Optional[str] = None
    version_date: Optional[str] = None
    selected_version: Optional[str] = None
    version_code: Optional[int] = None
    integration_model: Optional[str] = None
    apk_sha256: Optional[str] = None


class ComparisonRequest(BaseModel):
    app_a: SelectedAppMetadata
    app_b: SelectedAppMetadata
    download_apks: bool = True


class ApkDownloadInfo(BaseModel):
    app_id: str
    success: bool
    output_dir: str
    apk_files: list[str]
    error: Optional[str] = None


class ComparisonRequestResponse(BaseModel):
    comparison_id: str
    status: str
    message: str
    app_a: SelectedAppMetadata
    app_b: SelectedAppMetadata
    messages: list[str] = []
    apk_downloads: list[ApkDownloadInfo] = []


class VersionAppInfo(BaseModel):
    id_app: str
    version: str
    version_code: Optional[int] = None
    fecha_version: Optional[str] = None
    categoria: Optional[str] = None
    modelo_integracion: str
    apk_sha256: Optional[str] = None
    estado_mobsf: str
    hash_mobsf: Optional[str] = None
    ruta_informe_mobsf: Optional[str] = None
    ruta_apk: Optional[str] = None


class MobSFReportInfo(BaseModel):
    available: bool
    hash_mobsf: Optional[str] = None
    ruta_informe: Optional[str] = None
    file_name: Optional[str] = None
    scan_type: Optional[str] = None
    json_report: Optional[dict[str, Any]] = None


class VersionReportInfo(BaseModel):
    version_app: VersionAppInfo
    mobsf_report: MobSFReportInfo


class ComparisonAnalysisResponse(BaseModel):
    comparison_id: str
    status: str
    message: str
    messages: list[str]
    app_a: VersionReportInfo
    app_b: VersionReportInfo
    id_indice_aplicado: Optional[str] = None
    comparison: dict[str, Any]
    dashboard: dict[str, Any] = Field(default_factory=dict)
    comparison_json: str
    comparison_artifact_path: Optional[str] = None
