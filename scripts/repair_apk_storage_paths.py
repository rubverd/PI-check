#!/usr/bin/env python3
"""Repara version_app.ruta_apk para que apunte al almacenamiento gestionado.

Pensado para ejecutarse dentro del contenedor backend:

    docker compose exec backend python scripts/repair_apk_storage_paths.py

También puede ejecutarse desde el host si DATABASE_URL apunta a PostgreSQL y el
paquete backend/app es importable desde el repo.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if BACKEND_DIR.exists():
    sys.path.insert(0, str(BACKEND_DIR))

from app.infrastructure.external.apk_metadata_extractor import (
    calculate_sha256,
)  # noqa: E402
from app.infrastructure.persistence.models.app_version_model import (
    AppVersionModel,
)  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("repair-apk-storage")

SUPPORTED_EXTENSIONS = {".apk", ".xapk", ".apks", ".apkm"}


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("[REPAIR] DATABASE_URL no está configurada.")
        return 2

    apk_storage_dir = Path(os.getenv("APK_STORAGE_DIR", "/app/artifacts/apks"))
    apk_tmp_dir = Path(os.getenv("APK_TMP_DIR", "/app/artifacts/tmp/apks"))

    engine = create_engine(database_url)
    repaired = 0
    warnings = 0

    with Session(engine) as session:
        versions = session.execute(select(AppVersionModel)).scalars().all()

        for version in versions:
            current_path = Path(version.ruta_apk) if version.ruta_apk else None

            if _is_valid_managed_path(current_path, apk_storage_dir):
                continue

            if current_path is None:
                logger.warning(
                    "[REPAIR] ruta_apk NULL para %s %s. No hay archivo origen que mover.",
                    version.id_app,
                    version.version,
                )
                warnings += 1
                continue

            if not current_path.exists():
                logger.warning(
                    "[REPAIR] No se puede reparar ruta_apk porque el archivo no existe: %s",
                    current_path,
                )
                warnings += 1
                continue

            if current_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                logger.warning(
                    "[REPAIR] Extensión no soportada para %s: %s",
                    current_path,
                    current_path.suffix,
                )
                warnings += 1
                continue

            apk_sha256 = version.apk_sha256 or calculate_sha256(current_path)
            target_path = _target_path(
                storage_dir=apk_storage_dir,
                id_app=version.id_app,
                version=version.version,
                apk_sha256=apk_sha256,
                suffix=current_path.suffix,
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if current_path.resolve() != target_path.resolve():
                if target_path.exists():
                    if _is_under(current_path, apk_tmp_dir):
                        current_path.unlink()
                elif _is_under(current_path, apk_tmp_dir):
                    shutil.move(str(current_path), str(target_path))
                    logger.info(
                        "[REPAIR] APK movido de tmp a almacenamiento gestionado: %s -> %s",
                        current_path,
                        target_path,
                    )
                else:
                    shutil.copy2(current_path, target_path)
                    logger.info(
                        "[REPAIR] APK copiado a almacenamiento gestionado: %s -> %s",
                        current_path,
                        target_path,
                    )

            version.apk_sha256 = apk_sha256
            version.ruta_apk = str(target_path)
            repaired += 1
            logger.info(
                "[REPAIR] ruta_apk reparada para %s %s: %s",
                version.id_app,
                version.version,
                target_path,
            )

        session.commit()

    logger.info("[REPAIR] Finalizado. Reparadas=%s avisos=%s", repaired, warnings)
    return 0


def _target_path(
    storage_dir: Path,
    id_app: str,
    version: str,
    apk_sha256: str,
    suffix: str,
) -> Path:
    safe_app_id = _safe_path_component(id_app)
    safe_version = _safe_path_component(version)
    return (
        storage_dir
        / safe_app_id
        / safe_version
        / f"{safe_app_id}_{safe_version}_{apk_sha256[:12]}{suffix.lower()}"
    )


def _is_valid_managed_path(path: Path | None, storage_dir: Path) -> bool:
    if path is None or not path.exists() or not path.is_file():
        return False

    return _is_under(path, storage_dir)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_parent = parent.resolve()
    except OSError:
        return False

    return resolved_path == resolved_parent or resolved_parent in resolved_path.parents


def _safe_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned[:120] or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
