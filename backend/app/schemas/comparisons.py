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
    messages: list[str] = Field(default_factory=list)
    apk_downloads: list[ApkDownloadInfo] = Field(default_factory=list)


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


class MastgEvaluationInfo(BaseModel):
    id_mastg: str
    resultado: str
    ruta_resultado_json: Optional[str] = None
    mensaje_error: Optional[str] = None
    fecha_ejecucion: Optional[str] = None


class PrivacyIndexResultInfo(BaseModel):
    id_indice: str
    nombre_indice: str
    pruebas_superadas: int
    pruebas_totales: int
    pruebas_fallidas: int = 0
    pruebas_error: int = 0
    pruebas_no_aplicables: int = 0
    puntuacion: float


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
    resultados_mastg: list[MastgEvaluationInfo] = Field(default_factory=list)
    resultados_indices: list[PrivacyIndexResultInfo] = Field(default_factory=list)


class ComparisonAnalysisResponse(BaseModel):
    comparison_id: str
    status: str
    message: str
    messages: list[str]
    app_a: VersionReportInfo
    app_b: VersionReportInfo
    id_indice_aplicado: Optional[str] = None