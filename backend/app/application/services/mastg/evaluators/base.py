from __future__ import annotations

import ipaddress
import re
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.application.services.mastg.models import (
    MastgEvaluationStatus,
    MastgRuleResult,
)


HTTP_URL_RE = re.compile(r"http://[^\s\"'<>),;\]]+", re.IGNORECASE)


def ensure_rule_result(value: Any) -> MastgRuleResult:
    if isinstance(value, MastgRuleResult):
        return value

    if isinstance(value, dict):
        raw_status = value.get("status", MastgEvaluationStatus.ERROR.value)
        try:
            status = MastgEvaluationStatus(raw_status)
        except ValueError:
            status = MastgEvaluationStatus.ERROR

        return MastgRuleResult(
            status=status,
            summary=str(value.get("summary", "")),
            details=value.get("details") or {},
            evidence=value.get("evidence") or [],
            recommendation=value.get("recommendation"),
            error=value.get("error"),
        )

    return MastgRuleResult.error_result(
        "El evaluador devolvió un tipo de resultado no soportado.",
        error=f"Unsupported result type: {type(value)!r}",
    )


def walk_values(value: Any) -> Iterator[Any]:
    if isinstance(value, dict):
        for item in value.values():
            yield item
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield item
            yield from walk_values(item)


def walk_items(value: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from walk_items(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_items(item)


def iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def find_values_by_key(value: Any, wanted_keys: Iterable[str]) -> list[Any]:
    normalized = {key.lower() for key in wanted_keys}
    found: list[Any] = []

    for key, item in walk_items(value):
        if key.lower() in normalized:
            found.append(item)

    return found


def extract_http_urls(value: Any) -> list[str]:
    urls: set[str] = set()

    for text in iter_strings(value):
        for match in HTTP_URL_RE.findall(text):
            urls.add(match.rstrip(".,"))

    return sorted(urls)


def is_public_http_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.scheme.lower() != "http":
        return False

    host = parsed.hostname
    if not host:
        return False

    host_lower = host.lower()

    ignored_hosts = {
        "localhost",
        "schemas.android.com",
        "www.w3.org",
        "apache.org",
        "xmlpull.org",
    }

    if host_lower in ignored_hosts:
        return False

    if host_lower.endswith(".android.com"):
        return False

    try:
        ip = ipaddress.ip_address(host_lower)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except ValueError:
        return True


def limit_evidence(items: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    return items[:limit]


def scan_apk_dex_patterns(
    apk_path: Path,
    patterns: Mapping[str, Iterable[str]],
    *,
    max_evidence: int = 50,
) -> dict[str, list[dict[str, Any]]]:
    findings: dict[str, list[dict[str, Any]]] = {name: [] for name in patterns}

    with zipfile.ZipFile(apk_path) as apk:
        dex_names = [
            name
            for name in apk.namelist()
            if name.startswith("classes") and name.endswith(".dex")
        ]

        for dex_name in dex_names:
            content = apk.read(dex_name)

            for category, category_patterns in patterns.items():
                for pattern in category_patterns:
                    raw_pattern = pattern.encode("utf-8", errors="ignore")
                    if raw_pattern and raw_pattern in content:
                        if len(findings[category]) < max_evidence:
                            findings[category].append(
                                {
                                    "file": dex_name,
                                    "pattern": pattern,
                                }
                            )

    return {
        category: evidence
        for category, evidence in findings.items()
        if evidence
    }


def summarize_findings(findings: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "categories": sorted(findings.keys()),
        "total_categories": len(findings),
        "total_matches": sum(len(items) for items in findings.values()),
    }
