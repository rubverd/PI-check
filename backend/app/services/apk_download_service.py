import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.schemas.comparisons import ApkDownloadInfo

logger = logging.getLogger("pi-check")


def download_apk_with_apkeep(
    app_id: str,
    output_dir: Path,
    source: str = "apk-pure",
    timeout_seconds: int = 240,
) -> ApkDownloadInfo:
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "apkeep",
        "-a",
        app_id,
    ]

    if source:
        command.extend(["-d", source])

    command.append(str(output_dir))

    logger.info("Ejecutando descarga APK: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        apk_files = [
            str(path)
            for path in output_dir.rglob("*")
            if path.suffix.lower() in {".apk", ".xapk", ".apkm", ".apks"}
        ]

        success = result.returncode == 0 and len(apk_files) > 0

        if success:
            logger.info("APK descargado correctamente para %s", app_id)
            logger.info("Archivos encontrados: %s", apk_files)
        else:
            logger.error("Error descargando %s", app_id)
            logger.error("stdout: %s", result.stdout)
            logger.error("stderr: %s", result.stderr)

        return ApkDownloadInfo(
            app_id=app_id,
            success=success,
            output_dir=str(output_dir),
            apk_files=apk_files,
            error=None if success else result.stderr or result.stdout,
        )

    except FileNotFoundError:
        return ApkDownloadInfo(
            app_id=app_id,
            success=False,
            output_dir=str(output_dir),
            apk_files=[],
            error="No se ha encontrado el comando 'apkeep'. Comprueba que está instalado en WSL.",
        )

    except subprocess.TimeoutExpired:
        return ApkDownloadInfo(
            app_id=app_id,
            success=False,
            output_dir=str(output_dir),
            apk_files=[],
            error=f"La descarga ha superado el tiempo máximo de {timeout_seconds} segundos.",
        )

    except Exception as exc:
        logger.exception("Error inesperado descargando APK para %s", app_id)

        return ApkDownloadInfo(
            app_id=app_id,
            success=False,
            output_dir=str(output_dir),
            apk_files=[],
            error=f"Error inesperado descargando APK: {exc}",
        )


def download_apks_with_apkeep_in_parallel(
    app_downloads: list[tuple[str, Path]],
    source: str = "apk-pure",
    timeout_seconds: int = 240,
) -> list[ApkDownloadInfo]:
    """
    Descarga varios APKs en paralelo utilizando apkeep.

    Cada elemento de app_downloads contiene:
    - app_id: identificador del paquete Android.
    - output_dir: carpeta específica donde guardar la descarga de esa app.
    """
    if not app_downloads:
        return []

    logger.info("Iniciando descarga paralela de %s APKs", len(app_downloads))

    results: list[ApkDownloadInfo | None] = [None] * len(app_downloads)

    max_workers = min(len(app_downloads), 4)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                download_apk_with_apkeep,
                app_id,
                output_dir,
                source,
                timeout_seconds,
            ): index
            for index, (app_id, output_dir) in enumerate(app_downloads)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            app_id, output_dir = app_downloads[index]

            try:
                results[index] = future.result()
            except Exception as exc:
                logger.exception("Error en la descarga paralela de %s", app_id)

                results[index] = ApkDownloadInfo(
                    app_id=app_id,
                    success=False,
                    output_dir=str(output_dir),
                    apk_files=[],
                    error=f"Error inesperado en descarga paralela: {exc}",
                )

    final_results = [result for result in results if result is not None]

    logger.info("Descarga paralela finalizada")

    return final_results