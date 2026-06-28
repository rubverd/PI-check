from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
import logging
import re
import shutil
import subprocess
import zipfile
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

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
    apk_sha256: str | None
    app_label: str | None = None
    icon: str | None = None
    icon_source: str | None = None


def extract_apk_metadata(
    apk_path: Path,
    fallback_app_id: str,
    fallback_version: str | None = None,
    fallback_category: str | None = None,
    fallback_version_date: str | None = None,
    extract_icon: bool = True,
) -> ExtractedApkMetadata:
    apk_sha256 = calculate_sha256(apk_path)

    logger.info("[METADATA] Calculado SHA256 para %s: %s", apk_path, apk_sha256)

    metadata_apk_path = _prepare_apk_for_metadata_extraction(apk_path)

    if metadata_apk_path is not None:
        logger.info(
            "[METADATA] Archivo usado para extracción de metadatos: %s",
            metadata_apk_path,
        )
        aapt_metadata = _extract_with_aapt(metadata_apk_path)
    else:
        logger.warning(
            "[METADATA] No se encontró APK interno para extraer metadatos en %s",
            apk_path,
        )
        aapt_metadata = {}

    id_app = aapt_metadata.get("package_name") or fallback_app_id

    raw_version = (
        aapt_metadata.get("version_name")
        or (
            fallback_version
            if is_valid_version_string(fallback_version)
            else None
        )
        or f"unknown-{apk_sha256[:12]}"
    )

    version = normalize_version(raw_version, apk_sha256)

    version_code = _to_int_or_none(aapt_metadata.get("version_code"))

    fecha_version = parse_date_or_none(fallback_version_date)

    app_label = aapt_metadata.get("app_label")
    icon_url = None
    icon_source = None

    if extract_icon and metadata_apk_path is not None:
        try:
            icon_result = _extract_icon_to_public_storage(
                apk_path=metadata_apk_path,
                preferred_icon_paths=aapt_metadata.get("icon_paths", []),
                id_app=id_app,
                version=version,
                app_label=app_label,
            )
            if icon_result is not None:
                icon_url, icon_source = icon_result
        except Exception as exc:
            logger.warning(
                "[ICON] No se pudo extraer/normalizar icono para %s: %s",
                metadata_apk_path,
                exc,
            )

    modelo_integracion = detect_integration_model(apk_path)

    logger.info(
        "[METADATA] Resultado extracción: id_app=%s version=%s "
        "version_code=%s integration=%s",
        id_app,
        version,
        version_code,
        modelo_integracion.value,
    )

    return ExtractedApkMetadata(
        id_app=id_app,
        version=version,
        version_code=version_code,
        fecha_version=fecha_version,
        categoria=fallback_category,
        modelo_integracion=modelo_integracion,
        apk_sha256=apk_sha256,
        app_label=app_label,
        icon=icon_url,
        icon_source=icon_source,
    )


def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def detect_integration_model(file_path: Path) -> IntegrationModel:
    markers = [
        "android.permission.health",
        "androidx.health.connect",
        "android.health.connect",
        "HealthConnectClient",
    ]

    try:
        found_markers = find_markers(file_path, markers)

        if found_markers:
            logger.info(
                "[INTEGRATION] Marcadores Health Connect encontrados en %s: %s",
                file_path,
                found_markers,
            )
            return IntegrationModel.HEALTH_CONNECT

        logger.info(
            "[INTEGRATION] No se encontraron marcadores Health Connect en %s",
            file_path,
        )

        return IntegrationModel.LEGACY

    except Exception as exc:
        logger.warning(
            "[INTEGRATION] No se pudo detectar modelo de integración para %s: %s",
            file_path,
            exc,
        )

        return IntegrationModel.UNKNOWN


def find_markers(file_path: Path, markers: list[str]) -> list[str]:
    marker_bytes: list[tuple[str, bytes]] = []

    for marker in markers:
        marker_bytes.append((marker, marker.encode("utf-8")))
        marker_bytes.append((marker, marker.encode("utf-16le")))

    suffix = file_path.suffix.lower()

    if suffix in {".xapk", ".apks", ".apkm", ".zip"}:
        return _zip_find_markers(file_path, marker_bytes)

    return _file_find_markers(file_path, marker_bytes)


def is_valid_version_string(value: str | None) -> bool:
    if value is None:
        return False

    clean_value = value.strip()

    invalid_values = {
        "",
        "varies with device",
        "varía según el dispositivo",
        "varies",
        "unknown",
        "none",
        "null",
    }

    return clean_value.lower() not in invalid_values


def normalize_version(version: str, apk_sha256: str) -> str:
    clean_version = version.strip()

    if not is_valid_version_string(clean_version):
        return f"unknown-{apk_sha256[:12]}"

    return clean_version[:100]


def parse_date_or_none(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _prepare_apk_for_metadata_extraction(file_path: Path) -> Path | None:
    suffix = file_path.suffix.lower()

    if suffix == ".apk":
        return file_path

    if suffix not in {".xapk", ".apks", ".apkm", ".zip"}:
        return None

    if not zipfile.is_zipfile(file_path):
        logger.warning("[METADATA] El archivo no es ZIP válido: %s", file_path)
        return None

    extraction_dir = file_path.parent / "_metadata_extracted" / file_path.stem
    extraction_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(file_path, "r") as archive:
        apk_members = [
            member
            for member in archive.infolist()
            if not member.is_dir()
            and member.filename.lower().endswith(".apk")
        ]

        if not apk_members:
            return None

        selected_member = sorted(apk_members, key=_apk_member_priority)[0]
        output_apk = extraction_dir / Path(selected_member.filename).name

        logger.info(
            "[METADATA] Extrayendo APK interno para metadatos: %s -> %s",
            selected_member.filename,
            output_apk,
        )

        with archive.open(selected_member, "r") as source, output_apk.open("wb") as target:
            shutil.copyfileobj(source, target)

        return output_apk


def _apk_member_priority(member: zipfile.ZipInfo) -> tuple[int, int]:
    filename = Path(member.filename).name.lower()

    if filename == "base.apk":
        return (0, -member.file_size)

    if "base" in filename:
        return (1, -member.file_size)

    if "universal" in filename:
        return (2, -member.file_size)

    if filename.startswith("split_config"):
        return (10, -member.file_size)

    return (5, -member.file_size)


def _extract_with_aapt(apk_path: Path) -> dict[str, object]:
    if apk_path.suffix.lower() != ".apk":
        return {}

    commands = [
        ["aapt", "dump", "badging", str(apk_path)],
        ["aapt2", "dump", "badging", str(apk_path)],
    ]

    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                logger.info(
                    "[METADATA] %s no pudo analizar %s: %s",
                    command[0],
                    apk_path,
                    result.stderr,
                )
                continue

            return _parse_aapt_badging(result.stdout)

        except FileNotFoundError:
            logger.info("[METADATA] %s no está instalado.", command[0])
            continue

        except subprocess.TimeoutExpired:
            logger.warning(
                "[METADATA] %s superó el tiempo máximo analizando %s",
                command[0],
                apk_path,
            )
            continue

        except Exception as exc:
            logger.warning(
                "[METADATA] Error usando %s sobre %s: %s",
                command[0],
                apk_path,
                exc,
            )
            continue

    logger.warning(
        "[METADATA] No se pudieron extraer metadatos con aapt/aapt2 para %s",
        apk_path,
    )

    return {}


def _parse_aapt_badging(output: str) -> dict[str, object]:
    metadata: dict[str, object] = {}

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

    app_label = _extract_application_label(output)
    icon_paths = _extract_application_icon_paths(output)

    if app_label:
        metadata["app_label"] = app_label

    if icon_paths:
        metadata["icon_paths"] = icon_paths

    return metadata



def _extract_application_label(output: str) -> str | None:
    for prefix in ("application-label-es:", "application-label-es-ES:", "application-label:", "application-label-en:"):
        line = next((line for line in output.splitlines() if line.startswith(prefix)), None)
        if line:
            label = _extract_first_quoted_value(line)
            if label:
                return label

    application_line = next(
        (line for line in output.splitlines() if line.startswith("application:")),
        None,
    )
    if application_line:
        label = _extract_quoted_value(application_line, "label")
        if label:
            return label

    launcher_line = next(
        (line for line in output.splitlines() if "launchable-activity:" in line),
        None,
    )
    if launcher_line:
        return _extract_quoted_value(launcher_line, "label")

    return None


def _extract_application_icon_paths(output: str) -> list[str]:
    density_candidates: list[tuple[int, str]] = []
    fallback_candidates: list[str] = []

    for line in output.splitlines():
        density_match = re.match(r"application-icon-(\d+):'([^']+)'", line)
        if density_match:
            density_candidates.append((int(density_match.group(1)), density_match.group(2)))
            continue

        if line.startswith("application:"):
            icon_path = _extract_quoted_value(line, "icon")
            if icon_path:
                fallback_candidates.append(icon_path)

    ordered = [path for _, path in sorted(density_candidates, key=lambda item: item[0], reverse=True)]
    ordered.extend(path for path in fallback_candidates if path not in ordered)
    return ordered


def _extract_first_quoted_value(text: str) -> str | None:
    match = re.search(r"'([^']+)'", text)
    if match:
        return match.group(1)
    return None


def _extract_icon_to_public_storage(
    apk_path: Path,
    preferred_icon_paths: list[str],
    id_app: str,
    version: str,
    app_label: str | None,
) -> tuple[str, str] | None:
    if not zipfile.is_zipfile(apk_path):
        return None

    public_root = Path("/app/artifacts/public")
    output_dir = public_root / "icons" / _safe_path_part(id_app) / _safe_path_part(version)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "icon.png"

    with zipfile.ZipFile(apk_path, "r") as archive:
        member = _select_icon_member(archive, preferred_icon_paths, apk_path)
        if member is not None:
            _write_raster_icon_member(archive, member, output_path)
            logger.info("[ICON] Icono raster extraído del APK: %s", output_path)
            return _public_icon_path(id_app, version), "apk_raster"

    logger.info(
        "[ICON] No se encontró icono raster/renderizable en %s; se genera fallback PNG.",
        apk_path,
    )
    _write_generated_icon(output_path, app_label or id_app)
    logger.info("[ICON] Icono generado como fallback: %s", output_path)
    return _public_icon_path(id_app, version), "generated"


def _select_icon_member(
    archive: zipfile.ZipFile,
    preferred_icon_paths: list[str],
    apk_path: Path,
) -> zipfile.ZipInfo | None:
    members_by_name = {member.filename: member for member in archive.infolist() if not member.is_dir()}

    for preferred_icon_path in preferred_icon_paths:
        preferred_member = members_by_name.get(preferred_icon_path)
        if preferred_member and _is_raster_icon_path(preferred_member.filename):
            return preferred_member

    for preferred_icon_path in preferred_icon_paths:
        if preferred_icon_path.lower().endswith(".xml"):
            resolved_member = _resolve_xml_icon_member(archive, apk_path, preferred_icon_path)
            if resolved_member is not None:
                return resolved_member

    candidates = [
        member
        for member in archive.infolist()
        if not member.is_dir() and _is_icon_raster_candidate(member.filename)
    ]

    if not candidates:
        return None

    return sorted(candidates, key=lambda member: (_icon_path_score(member.filename), member.file_size), reverse=True)[0]



def _write_raster_icon_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    output_path: Path,
) -> None:
    suffix = Path(member.filename).suffix.lower()
    with archive.open(member, "r") as source:
        icon_bytes = source.read()

    if suffix == ".png":
        output_path.write_bytes(icon_bytes)
        return

    if suffix == ".webp":
        with Image.open(BytesIO(icon_bytes)) as image:
            image.save(output_path, format="PNG")
        return

    raise ValueError(f"Recurso de icono no soportado: {member.filename}")


def _resolve_xml_icon_member(
    archive: zipfile.ZipFile,
    apk_path: Path,
    xml_path: str,
) -> zipfile.ZipInfo | None:
    xmltree_output = _dump_xmltree(apk_path, xml_path)
    if not xmltree_output:
        return None

    members_by_name = {member.filename: member for member in archive.infolist() if not member.is_dir()}
    for referenced_path in _candidate_resource_paths_from_xmltree(xmltree_output, archive):
        member = members_by_name.get(referenced_path)
        if member is not None and _is_raster_icon_path(member.filename):
            logger.info("[ICON] XML %s resuelto a recurso raster %s", xml_path, member.filename)
            return member

    logger.info("[ICON] XML %s no apunta a un raster extraíble; se usará fallback generado.", xml_path)
    return None


def _dump_xmltree(apk_path: Path, xml_path: str) -> str | None:
    for command_name in ("aapt", "aapt2"):
        try:
            result = subprocess.run(
                [command_name, "dump", "xmltree", str(apk_path), xml_path],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            logger.warning("[ICON] %s dump xmltree superó el tiempo máximo para %s", command_name, xml_path)
            continue

        if result.returncode == 0:
            return result.stdout

        logger.info("[ICON] %s dump xmltree falló para %s: %s", command_name, xml_path, result.stderr)

    return None


def _candidate_resource_paths_from_xmltree(
    xmltree_output: str,
    archive: zipfile.ZipFile,
) -> list[str]:
    names = {member.filename for member in archive.infolist() if not member.is_dir()}
    raster_names = sorted(name for name in names if _is_raster_icon_path(name))
    candidates: list[str] = []

    for match in re.finditer(r'Raw: "@([^"\s]+)"', xmltree_output):
        ref = match.group(1)
        candidates.extend(_resource_ref_to_archive_paths(ref, names))

    for match in re.finditer(r'@(?:[^:/]+:)?(?:drawable|mipmap)/([A-Za-z0-9_.-]+)', xmltree_output):
        resource_name = match.group(1)
        candidates.extend(_resource_name_to_raster_paths(resource_name, raster_names))

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate in names and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def _resource_ref_to_archive_paths(ref: str, archive_names: set[str]) -> list[str]:
    clean_ref = ref.removeprefix("android:")
    if clean_ref.startswith(("res/drawable", "res/mipmap")):
        return [clean_ref] if clean_ref in archive_names else []

    match = re.search(r'(?:drawable|mipmap)/([A-Za-z0-9_.-]+)$', clean_ref)
    if match:
        raster_names = [name for name in archive_names if _is_raster_icon_path(name)]
        return _resource_name_to_raster_paths(match.group(1), raster_names)

    return []


def _resource_name_to_raster_paths(resource_name: str, raster_names: list[str]) -> list[str]:
    return sorted(
        (
            name
            for name in raster_names
            if Path(name).stem == resource_name
            and (name.startswith("res/drawable") or name.startswith("res/mipmap"))
        ),
        key=lambda name: (_icon_path_score(name), _resource_density_score(name), len(name)),
        reverse=True,
    )


def _write_generated_icon(output_path: Path, label: str) -> None:
    initials = _initials_for_label(label)
    background = _color_for_label(label)
    image = Image.new("RGBA", (256, 256), background)
    draw = ImageDraw.Draw(image)
    font = _load_icon_font(96)
    bbox = draw.textbbox((0, 0), initials, font=font)
    x = (256 - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (256 - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.text((x, y), initials, fill=(255, 255, 255, 255), font=font)
    image.save(output_path, format="PNG")


def _initials_for_label(label: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", label)
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return "".join(word[0] for word in words[:2]).upper()


def _color_for_label(label: str) -> tuple[int, int, int, int]:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return (64 + digest[0] % 128, 64 + digest[1] % 128, 64 + digest[2] % 128, 255)


def _load_icon_font(size: int) -> ImageFont.ImageFont:
    for font_path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _public_icon_path(id_app: str, version: str) -> str:
    return f"/static/icons/{_safe_path_part(id_app)}/{_safe_path_part(version)}/icon.png"


def _resource_density_score(path: str) -> int:
    lower = path.lower()
    density_scores = {
        "xxxhdpi": 600,
        "xxhdpi": 500,
        "xhdpi": 400,
        "hdpi": 300,
        "mdpi": 200,
    }
    for density, score in density_scores.items():
        if density in lower:
            return score
    return 0

def _is_icon_raster_candidate(filename: str) -> bool:
    lower = filename.lower()
    if not _is_raster_icon_path(lower):
        return False
    if not (lower.startswith("res/mipmap") or lower.startswith("res/drawable")):
        return False

    name = Path(lower).stem
    keywords = ("ic_launcher", "launcher", "app_icon", "icon")
    return any(keyword in name for keyword in keywords)


def _is_raster_icon_path(path: str) -> bool:
    lower = path.lower()
    return lower.endswith((".png", ".webp")) and not lower.endswith(".xml")


def _icon_path_score(path: str) -> int:
    lower = path.lower()
    score = 0
    density_scores = {
        "xxxhdpi": 600,
        "xxhdpi": 500,
        "xhdpi": 400,
        "hdpi": 300,
        "mdpi": 200,
    }
    for density, density_score in density_scores.items():
        if density in lower:
            score += density_score
            break

    if "ic_launcher" in lower:
        score += 80
    elif "launcher" in lower:
        score += 60
    elif "app_icon" in lower:
        score += 50
    elif "icon" in lower:
        score += 30

    if lower.endswith(".png"):
        score += 10
    elif lower.endswith(".webp"):
        score += 8

    return score


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    return cleaned[:120] or "unknown"

def _extract_quoted_value(text: str, key: str) -> str | None:
    match = re.search(rf"{key}='([^']+)'", text)

    if match:
        return match.group(1)

    return None


def _to_int_or_none(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _file_find_markers(
    file_path: Path,
    marker_bytes: list[tuple[str, bytes]],
) -> list[str]:
    found: set[str] = set()

    with file_path.open("rb") as file:
        previous = b""

        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            data = previous + chunk

            for marker, marker_value in marker_bytes:
                if marker_value in data:
                    found.add(marker)

            previous = data[-256:]

    return sorted(found)


def _zip_find_markers(
    file_path: Path,
    marker_bytes: list[tuple[str, bytes]],
) -> list[str]:
    found: set[str] = set()

    with zipfile.ZipFile(file_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            lower_name = member.filename.lower()

            if not lower_name.endswith((".apk", ".dex", ".xml", ".json", ".txt")):
                continue

            with archive.open(member, "r") as file:
                previous = b""

                while True:
                    chunk = file.read(1024 * 1024)

                    if not chunk:
                        break

                    data = previous + chunk

                    for marker, marker_value in marker_bytes:
                        if marker_value in data:
                            found.add(marker)

                    previous = data[-256:]

    return sorted(found)