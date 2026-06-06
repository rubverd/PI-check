from __future__ import annotations

import logging
import os
import re
import zipfile
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

logger = logging.getLogger("pi-check")


@dataclass(frozen=True)
class TextSource:
    name: str
    text: str


@dataclass(frozen=True)
class PatternMatch:
    source: str
    value: str


class MastgAnalysisContext:
    """Contexto y utilidades compartidas para pruebas MASTG-lite estáticas."""

    def __init__(
        self,
        artifact_path: Path,
        id_app: str,
        version: str,
        max_member_bytes: int | None = None,
        max_total_bytes: int | None = None,
    ):
        self.artifact_path = artifact_path
        self.id_app = id_app
        self.version = version
        self.max_member_bytes = max_member_bytes or int(
            os.getenv("MASTG_MAX_MEMBER_BYTES", str(25 * 1024 * 1024))
        )
        self.max_total_bytes = max_total_bytes or int(
            os.getenv("MASTG_MAX_TOTAL_BYTES", str(90 * 1024 * 1024))
        )

    @cached_property
    def text_sources(self) -> list[TextSource]:
        sources = list(self._collect_text_sources(self.artifact_path, self.artifact_path.name))
        logger.info(
            "[MASTG] Fuentes textuales preparadas para app_id=%s version=%s: %s",
            self.id_app,
            self.version,
            len(sources),
        )
        return sources

    @cached_property
    def combined_text(self) -> str:
        return "\n".join(source.text for source in self.text_sources)

    def find_patterns(
        self,
        patterns: list[str],
        *,
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> list[PatternMatch]:
        results: list[PatternMatch] = []
        flags = 0 if case_sensitive else re.IGNORECASE

        for source in self.text_sources:
            for pattern in patterns:
                if re.search(re.escape(pattern), source.text, flags):
                    results.append(PatternMatch(source=source.name, value=pattern))
                    if len(results) >= max_results:
                        return self._deduplicate_matches(results)

        return self._deduplicate_matches(results)

    def find_regex(
        self,
        regex: str,
        *,
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> list[PatternMatch]:
        results: list[PatternMatch] = []
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(regex, flags)

        for source in self.text_sources:
            for match in compiled.finditer(source.text):
                results.append(PatternMatch(source=source.name, value=match.group(0)))
                if len(results) >= max_results:
                    return self._deduplicate_matches(results)

        return self._deduplicate_matches(results)

    def find_http_urls(self, max_results: int = 20) -> list[str]:
        matches = self.find_regex(
            r"http://[^\s'\"<>\\)\]}]+",
            case_sensitive=False,
            max_results=max_results,
        )
        return [match.value for match in matches[:max_results]]

    def _collect_text_sources(self, path: Path, label: str) -> list[TextSource]:
        if not path.exists():
            return []

        try:
            if zipfile.is_zipfile(path):
                return self._collect_zip_sources(path, label)

            data = path.read_bytes()[: self.max_total_bytes]
            return [TextSource(name=label, text=self._decode_bytes(data))]
        except Exception as exc:
            logger.warning("[MASTG] No se pudo leer %s: %s", path, exc)
            return []

    def _collect_zip_sources(self, path: Path, label: str) -> list[TextSource]:
        sources: list[TextSource] = []
        consumed = 0

        with zipfile.ZipFile(path, "r") as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue

                if consumed >= self.max_total_bytes:
                    break

                member_name = f"{label}!{member.filename}"
                if member.file_size > self.max_member_bytes:
                    logger.info(
                        "[MASTG] Se omite miembro grande %s (%s bytes)",
                        member_name,
                        member.file_size,
                    )
                    continue

                try:
                    with archive.open(member, "r") as source:
                        data = source.read(self.max_member_bytes)
                except Exception as exc:
                    logger.info("[MASTG] No se pudo leer miembro %s: %s", member_name, exc)
                    continue

                consumed += len(data)
                sources.append(TextSource(name=member_name, text=self._decode_bytes(data)))

                if member.filename.lower().endswith(".apk") and zipfile.is_zipfile(path):
                    sources.extend(self._collect_nested_apk_sources(data, member_name))

        return sources

    def _collect_nested_apk_sources(self, data: bytes, label: str) -> list[TextSource]:
        sources: list[TextSource] = []

        try:
            from io import BytesIO

            with zipfile.ZipFile(BytesIO(data), "r") as archive:
                for member in archive.infolist():
                    if member.is_dir() or member.file_size > self.max_member_bytes:
                        continue

                    try:
                        with archive.open(member, "r") as source:
                            member_data = source.read(self.max_member_bytes)
                    except Exception:
                        continue

                    sources.append(
                        TextSource(
                            name=f"{label}!{member.filename}",
                            text=self._decode_bytes(member_data),
                        )
                    )
        except Exception:
            return []

        return sources

    def _decode_bytes(self, data: bytes) -> str:
        # latin-1 conserva byte a byte para búsquedas sencillas sobre APK/DEX/XML binario.
        return "\n".join(
            [
                data.decode("utf-8", errors="ignore"),
                data.decode("utf-16le", errors="ignore"),
                data.decode("latin-1", errors="ignore"),
            ]
        )

    def _deduplicate_matches(self, matches: list[PatternMatch]) -> list[PatternMatch]:
        seen: set[tuple[str, str]] = set()
        unique: list[PatternMatch] = []

        for match in matches:
            key = (match.source, match.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(match)

        return unique
