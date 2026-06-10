import os
from urllib.parse import urlparse


STATIC_PUBLIC_PREFIX = "/static/"


def build_public_artifact_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None

    clean_path = relative_path.strip()
    if not clean_path:
        return None

    clean_path = _normalize_picheck_static_path(clean_path)

    if clean_path.startswith(("http://", "https://")):
        return clean_path

    if not clean_path.startswith("/"):
        clean_path = f"/{clean_path}"

    public_base = os.getenv("PICHECK_PUBLIC_BASE_URL", "").strip()
    if public_base:
        return f"{public_base.rstrip('/')}{clean_path}"

    return clean_path


def _normalize_picheck_static_path(value: str) -> str:
    if value.startswith(STATIC_PUBLIC_PREFIX):
        return value

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.path.startswith(STATIC_PUBLIC_PREFIX):
        return parsed.path

    return value
