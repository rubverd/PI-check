from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
import logging
import re
import subprocess
import zipfile

from app.domain.value_objects.integration_model import IntegrationModel


logger = logging.getLogger("pi-check")


@dataclass
class ExtractedApkMetadata:
    id_app: str
    version: str
    version_code: int | None
    fecha_version: date | None
    categoria: str | None
    modelo_integracion: IntegrationModel
    apk_sha256: str


def extract_apk_metadata(
    apk_path: Path,
    fallback_app_id: str,
    fallback_version: str | None = None,
    fallback_category: str | None = None,
    fallback_version_date: str | None = None,
) -> ExtractedApkMetadata:
    apk_sha256 = calculate_sha256(apk_path)

    aapt_metadata = _extract_with_aapt(apk_path)

    id_app = aapt_metadata.get("package_name") or fallback_app_id

    raw_version = (
        aapt_metadata.get("version_name")
        or fallback_version
        or f"unknown-{apk_sha256[:12]}"
    )

    version = _normalize_version(raw_version, apk_sha256)

    version_code = _to_int_or_none(aapt_metadata.get("version_code"))

    fecha_version = _parse_date_or_none(fallback_version_date)

    modelo_integracion = detect_integration_model(apk_path)

    return ExtractedApkMetadata(
        id_app=id_app,
        version=version,
        version_code=version_code,
        fecha_version=fecha_version,
        categoria=fallback_category,
        modelo_integracion=modelo_integracion,
        apk_sha256=apk_sha256,
    )


def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def detect_integration_model(file_path: Path) -> IntegrationModel:
    """
    Detección inicial y conservadora.

    Busca cadenas relacionadas con Health Connect dentro del APK/XAPK/APKS/APKM.
    Más adelante puede sustituirse por análisis formal del AndroidManifest.xml
    usando apktool, JADX o aapt2.
    """
    markers = [
        "android.permission.health",
        "androidx.health.connect",
        "android.health.connect",
        "HealthConnectClient",
    ]

    try:
        found = _contains_any_marker(file_path, markers)

        if found:
            return IntegrationModel.HEALTH_CONNECT

        return IntegrationModel.LEGACY

    except Exception as exc:
        logger.warning(
            "No se pudo detectar modelo de integración para %s: %s",
            file_path,
            exc,
        )

        return IntegrationModel.UNKNOWN


def _extract_with_aapt(apk_path: Path) -> dict[str, str]:
    """
    Usa `aapt dump badging` si está disponible en la imagen Docker.

    Si aapt no está instalado o el archivo no es un APK estándar,
    devuelve un diccionario vacío.
    """
    if apk_path.suffix.lower() != ".apk":
        return {}

    command = [
        "aapt",
        "dump",
        "badging",
        str(apk_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            logger.info("aapt no pudo analizar %s: %s", apk_path, result.stderr)
            return {}

        return _parse_aapt_badging(result.stdout)

    except FileNotFoundError:
        logger.info("aapt no está instalado. Se usarán metadatos fallback.")
        return {}

    except subprocess.TimeoutExpired:
        logger.warning("aapt superó el tiempo máximo analizando %s", apk_path)
        return {}

    except Exception as exc:
        logger.warning("Error usando aapt sobre %s: %s", apk_path, exc)
        return {}


def _parse_aapt_badging(output: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    package_line = next(
        (line for line in output.splitlines() if line.startswith("package:")),
        None,
    )

    if not package_line:
        return metadata

    package_name = _extract_quoted_value(package_line, "name")
    version_code = _extract_quoted_value(package_line, "versionCode")
    version_name = _extract_quoted_value(package_line, "versionName")

    if package_name:
        metadata["package_name"] = package_name

    if version_code:
        metadata["version_code"] = version_code

    if version_name:
        metadata["version_name"] = version_name

    return metadata


def _extract_quoted_value(text: str, key: str) -> str | None:
    match = re.search(rf"{key}='([^']+)'", text)

    if match:
        return match.group(1)

    return None


def _normalize_version(version: str, apk_sha256: str) -> str:
    clean_version = version.strip()

    invalid_values = {
        "",
        "varies with device",
        "varía según el dispositivo",
        "varies",
        "unknown",
        "none",
        "null",
    }

    if clean_version.lower() in invalid_values:
        return f"unknown-{apk_sha256[:12]}"

    return clean_version[:100]


def _parse_date_or_none(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_int_or_none(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _contains_any_marker(file_path: Path, markers: list[str]) -> bool:
    marker_bytes = []

    for marker in markers:
        marker_bytes.append(marker.encode("utf-8"))
        marker_bytes.append(marker.encode("utf-16le"))

    suffix = file_path.suffix.lower()

    if suffix in {".xapk", ".apks", ".apkm", ".zip"}:
        return _zip_contains_any_marker(file_path, marker_bytes)

    return _file_contains_any_marker(file_path, marker_bytes)


def _file_contains_any_marker(file_path: Path, marker_bytes: list[bytes]) -> bool:
    with file_path.open("rb") as file:
        previous = b""

        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            data = previous + chunk

            if any(marker in data for marker in marker_bytes):
                return True

            previous = data[-256:]

    return False


def _zip_contains_any_marker(file_path: Path, marker_bytes: list[bytes]) -> bool:
    with zipfile.ZipFile(file_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            lower_name = member.filename.lower()

            if not lower_name.endswith((".apk", ".xml", ".json", ".txt")):
                continue

            with archive.open(member, "r") as file:
                previous = b""

                while True:
                    chunk = file.read(1024 * 1024)

                    if not chunk:
                        break

                    data = previous + chunk

                    if any(marker in data for marker in marker_bytes):
                        return True

                    previous = data[-256:]

    return False