import logging
import os
import subprocess
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

        if not success:
            logger.error("Error descargando %s: %s", app_id, result.stderr)

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