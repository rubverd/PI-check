import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter

from app.infrastructure.external.apkeep_client import download_apks_with_apkeep_in_parallel
from app.schemas.comparisons import (
    ApkDownloadInfo,
    ComparisonRequest,
    ComparisonRequestResponse,
)


router = APIRouter(
    prefix="/api/comparisons",
    tags=["comparisons"],
)


@router.post("/request", response_model=ComparisonRequestResponse)
def request_comparison(request: ComparisonRequest):
    comparison_id = str(uuid4())

    messages: list[str] = [
        f"Solicitud de comparación creada con identificador {comparison_id}.",
        f"Sin análisis previo comprobado para {request.app_a.title}.",
        f"Sin análisis previo comprobado para {request.app_b.title}.",
    ]

    apk_downloads: list[ApkDownloadInfo] = []

    if request.download_apks:
        messages.append(f"Descargando APK de {request.app_a.title}.")
        messages.append(f"Descargando APK de {request.app_b.title}.")

        apk_tmp_dir = os.getenv(
            "APK_TMP_DIR",
            os.getenv("APK_OUTPUT_DIR", "artifacts/tmp/apks"),
        )

        base_output_dir = Path(apk_tmp_dir) / comparison_id

        app_downloads = [
            (
                request.app_a.app_id,
                base_output_dir / request.app_a.app_id,
            ),
            (
                request.app_b.app_id,
                base_output_dir / request.app_b.app_id,
            ),
        ]

        apk_downloads = download_apks_with_apkeep_in_parallel(
            app_downloads=app_downloads,
            source="apk-pure",
            timeout_seconds=300,
        )

        if all(download.success for download in apk_downloads):
            status = "apks_downloaded"
            message = "Solicitud de comparación registrada y APKs descargados correctamente."
            messages.append("Ambas descargas finalizaron correctamente.")
        else:
            status = "apk_download_error"
            message = "La solicitud se registró, pero se produjo algún error durante la descarga de APKs."
            messages.append("Al menos una descarga no finalizó correctamente.")

    else:
        status = "requested"
        message = "Solicitud de comparación registrada correctamente. La descarga de APKs no fue solicitada."
        messages.append("Descarga de APKs omitida porque download_apks=false.")

    return ComparisonRequestResponse(
        comparison_id=comparison_id,
        status=status,
        message=message,
        app_a=request.app_a,
        app_b=request.app_b,
        messages=messages,
        apk_downloads=apk_downloads,
    )