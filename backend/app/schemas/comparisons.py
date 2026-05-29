from typing import Optional

from pydantic import BaseModel


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
    download_apks: bool = False


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