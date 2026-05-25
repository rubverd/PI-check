from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from app.schemas.comparisons import (
    ApkDownloadInfo,
    ComparisonRequest,
    ComparisonRequestResponse,
)
from app.services.apk_download_service import download_apk_with_apkeep

router = APIRouter(
    prefix="/api/comparisons",
    tags=["comparisons"],
)


@router.post("/request", response_model=ComparisonRequestResponse)
def request_comparison(request: ComparisonRequest):
    comparison_id = str(uuid4())

    apk_downloads: list[ApkDownloadInfo] = []

    if request.download_apks:
        base_output_dir = Path("artifacts") / "apks" / comparison_id

        apk_downloads.append(
            download_apk_with_apkeep(
                app_id=request.app_a.app_id,
                output_dir=base_output_dir / request.app_a.app_id,
            )
        )

        apk_downloads.append(
            download_apk_with_apkeep(
                app_id=request.app_b.app_id,
                output_dir=base_output_dir / request.app_b.app_id,
            )
        )

    return ComparisonRequestResponse(
        comparison_id=comparison_id,
        status="requested",
        message="Solicitud de comparación registrada correctamente.",
        app_a=request.app_a,
        app_b=request.app_b,
        apk_downloads=apk_downloads,
    )