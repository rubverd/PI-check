#!/usr/bin/env python3
"""Backfill visible names and public APK icons for registered local APKs.

Dry-run by default. Use --apply to persist changes.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.infrastructure.database.session import SessionLocal  # noqa: E402
from app.infrastructure.external.apk_metadata_extractor import extract_apk_metadata  # noqa: E402
from app.infrastructure.persistence.models.application_model import ApplicationModel  # noqa: E402
from app.infrastructure.persistence.models.app_version_model import AppVersionModel  # noqa: E402


def main() -> int:
    args = _parse_args()
    apply_changes = args.apply

    with SessionLocal() as db:
        rows = _load_versions_with_apks(db)
        updated_names = 0
        updated_icons = 0
        inspected = 0

        for app, versions in rows.items():
            if not _needs_backfill(app):
                continue

            for version in versions if args.all_versions else versions[:1]:
                apk_path = Path(version.ruta_apk or "")
                if not apk_path.is_file():
                    print(f"SKIP missing APK: {app.id_app} {version.version} {apk_path}")
                    continue

                inspected += 1
                metadata = extract_apk_metadata(
                    apk_path=apk_path,
                    fallback_app_id=app.id_app,
                    fallback_version=version.version,
                    fallback_category=version.categoria,
                    fallback_version_date=(version.fecha_version.isoformat() if version.fecha_version else None),
                )

                name_changed = False
                icon_changed = False

                if metadata.app_label and _is_bad_generated_name(app.nombre, app.id_app):
                    print(f"NAME {app.id_app}: {app.nombre!r} -> {metadata.app_label!r}")
                    if apply_changes:
                        app.nombre = metadata.app_label
                    name_changed = True

                if metadata.icon and _is_invalid_or_missing_icon(app.icono):
                    print(f"ICON {app.id_app}: {app.icono!r} -> {metadata.icon!r}")
                    if apply_changes:
                        app.icono = metadata.icon
                    icon_changed = True

                updated_names += int(name_changed)
                updated_icons += int(icon_changed)

                if name_changed or icon_changed or not args.all_versions:
                    break

        if apply_changes:
            db.commit()
        else:
            db.rollback()

    mode = "APPLY" if apply_changes else "DRY-RUN"
    print(f"{mode} inspected={inspected} updated_names={updated_names} updated_icons={updated_icons}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist updates in the database.")
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Inspect all APK versions instead of stopping at the newest candidate per app.",
    )
    return parser.parse_args()


def _load_versions_with_apks(db: Session) -> dict[ApplicationModel, list[AppVersionModel]]:
    stmt = (
        select(ApplicationModel, AppVersionModel)
        .join(AppVersionModel, AppVersionModel.id_app == ApplicationModel.id_app)
        .where(AppVersionModel.ruta_apk.is_not(None))
        .order_by(
            ApplicationModel.id_app.asc(),
            AppVersionModel.fecha_version.desc().nullslast(),
            AppVersionModel.version_code.desc().nullslast(),
            AppVersionModel.version.desc(),
        )
    )
    grouped: dict[ApplicationModel, list[AppVersionModel]] = {}
    for app, version in db.execute(stmt).all():
        grouped.setdefault(app, []).append(version)
    return grouped


def _needs_backfill(app: ApplicationModel) -> bool:
    return _is_bad_generated_name(app.nombre, app.id_app) or _is_invalid_or_missing_icon(app.icono)


def _is_invalid_or_missing_icon(icon: str | None) -> bool:
    if icon is None or not icon.strip():
        return True
    value = icon.strip()
    if value.startswith(("http://", "https://")):
        return False
    if value.startswith("/app/"):
        return True
    if value.startswith("/static/"):
        return not _static_file_exists(value)
    return False


def _static_file_exists(icon: str) -> bool:
    try:
        public_root = Path(os.getenv("PUBLIC_ARTIFACTS_DIR", "/app/artifacts/public")).resolve()
        icon_path = (public_root / icon.removeprefix("/static/")).resolve()
        return icon_path.is_file() and (icon_path == public_root or public_root in icon_path.parents)
    except OSError:
        return False


def _is_bad_generated_name(value: str | None, app_id: str) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    lower = normalized.lower()
    app_lower = app_id.lower()

    if not normalized:
        return True
    if re.fullmatch(r"[0-9a-f]{16,}", lower) or re.match(r"^[0-9a-f]{16,}[_-]", lower):
        return True
    if "@" in normalized and app_lower in lower:
        return True
    if lower == app_lower:
        return True
    if lower.startswith(("upload.", "manual.")):
        return True
    return lower.endswith((".apk", ".xapk", ".apks", ".apkm"))


if __name__ == "__main__":
    raise SystemExit(main())
