import os
from pathlib import Path
from typing import Any

import requests
import logging
from dotenv import load_dotenv

from app.domain.entities.mobsf_report import MobSFReport


load_dotenv()


MOBSF_URL = os.getenv("MOBSF_URL", "http://localhost:8001").rstrip("/")
MOBSF_API_KEY = os.getenv("MOBSF_API_KEY", "").strip()
MOBSF_TIMEOUT_SECONDS = int(os.getenv("MOBSF_TIMEOUT_SECONDS", "1800"))

logger = logging.getLogger("pi-check")

class MobSFClientError(Exception):
    """Error controlado durante la comunicación con MobSF."""


class MobSFClient:
    def __init__(
        self,
        mobsf_url: str = MOBSF_URL,
        api_key: str = MOBSF_API_KEY,
        timeout_seconds: int = MOBSF_TIMEOUT_SECONDS,
    ):
        self.mobsf_url = mobsf_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def check_health(self) -> dict[str, Any]:
        try:
            response = requests.get(
                self.mobsf_url,
                timeout=10,
                allow_redirects=True,
            )

            return {
                "mobsf_url": self.mobsf_url,
                "status_code": response.status_code,
                "final_url": response.url,
                "available": response.status_code < 500,
            }

        except requests.RequestException as exc:
            return {
                "mobsf_url": self.mobsf_url,
                "status_code": None,
                "final_url": None,
                "available": False,
                "error": str(exc),
            }

    def generate_json_report(self, apk_path: Path) -> MobSFReport:
        logger.info("MobSF: iniciando subida de archivo %s", apk_path)

        upload_response = self.upload_file(apk_path)

        logger.info("MobSF: subida completada. Respuesta: %s", upload_response)

        scan_hash = upload_response.get("hash")
        scan_type = upload_response.get("scan_type") or self._infer_scan_type(apk_path)
        file_name = upload_response.get("file_name") or apk_path.name

        if not scan_hash:
            raise MobSFClientError(
                f"MobSF no devolvió hash al subir el archivo {apk_path}"
            )

        logger.info(
            "MobSF: iniciando análisis. hash=%s, file_name=%s, scan_type=%s",
            scan_hash,
            file_name,
            scan_type,
        )

        scan_response = self.scan_file(
            scan_hash=scan_hash,
            file_name=file_name,
            scan_type=scan_type,
        )

        logger.info("MobSF: análisis finalizado. Respuesta parcial: %s", scan_response)

        logger.info("MobSF: solicitando informe JSON. hash=%s", scan_hash)

        json_report = self.download_json_report(scan_hash)

        logger.info(
            "MobSF: informe JSON recibido correctamente. Campos principales: %s",
            list(json_report.keys())[:20],
        )

        return MobSFReport(
            hash_mobsf=scan_hash,
            file_name=file_name,
            scan_type=scan_type,
            ruta_informe=None,
            json_report=json_report,
        )

    def upload_file(self, apk_path: Path) -> dict[str, Any]:
        if not apk_path.exists():
            raise MobSFClientError(f"No existe el archivo APK: {apk_path}")

        url = f"{self.mobsf_url}/api/v1/upload"
        last_response: requests.Response | None = None

        for content_type in self._candidate_content_types_for(apk_path):
            with apk_path.open("rb") as file:
                if content_type is None:
                    files = {
                        "file": (
                            apk_path.name,
                            file,
                        )
                    }
                    content_type_label = "sin Content-Type explícito"
                else:
                    files = {
                        "file": (
                            apk_path.name,
                            file,
                            content_type,
                        )
                    }
                    content_type_label = content_type

                logger.info(
                    "MobSF: intentando subida de %s con Content-Type=%s",
                    apk_path.name,
                    content_type_label,
                )

                response = requests.post(
                    url,
                    headers=self._headers(),
                    files=files,
                    timeout=self.timeout_seconds,
                )

            if response.status_code < 400:
                return self._parse_response(response, "subir archivo a MobSF")

            last_response = response

            if not self._is_retryable_upload_error(response):
                break

            logger.warning(
                "MobSF: fallo subiendo %s con Content-Type=%s. "
                "HTTP %s: %s. Probando alternativa...",
                apk_path.name,
                content_type_label,
                response.status_code,
                response.text[:300],
            )

        if last_response is None:
            raise MobSFClientError(f"No se pudo realizar la subida de {apk_path}")

        return self._parse_response(last_response, "subir archivo a MobSF")

    def scan_file(
        self,
        scan_hash: str,
        file_name: str,
        scan_type: str,
    ) -> dict[str, Any]:
        url = f"{self.mobsf_url}/api/v1/scan"

        response = requests.post(
            url,
            headers=self._headers(),
            data={
                "hash": scan_hash,
                "file_name": file_name,
                "scan_type": scan_type,
            },
            timeout=self.timeout_seconds,
        )

        return self._parse_response(response, "lanzar análisis MobSF")

    def download_json_report(self, scan_hash: str) -> dict[str, Any]:
        url = f"{self.mobsf_url}/api/v1/report_json"

        response = requests.post(
            url,
            headers=self._headers(),
            data={"hash": scan_hash},
            timeout=self.timeout_seconds,
        )

        return self._parse_response(response, "descargar informe JSON de MobSF")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}

        return {
            "Authorization": self.api_key,
            "X-Mobsf-Api-Key": self.api_key,
        }

    def _parse_response(
        self,
        response: requests.Response,
        action: str,
    ) -> dict[str, Any]:
        if response.status_code >= 400:
            raise MobSFClientError(
                f"Error al {action}. "
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise MobSFClientError(
                f"MobSF no devolvió JSON válido al {action}: {response.text[:500]}"
            ) from exc

        if isinstance(data, dict) and data.get("error"):
            raise MobSFClientError(f"MobSF devolvió error al {action}: {data}")

        if not isinstance(data, dict):
            raise MobSFClientError(
                f"Respuesta inesperada de MobSF al {action}: {data}"
            )

        return data

    def _infer_scan_type(self, apk_path: Path) -> str:
        suffix = apk_path.suffix.lower().replace(".", "")

        if suffix in {"apk", "xapk", "apks"}:
            return suffix

        return "apk"
    
    def _content_type_for(self, apk_path: Path) -> str:
        suffix = apk_path.suffix.lower()

        if suffix == ".apk":
            return "application/vnd.android.package-archive"

        if suffix in {".xapk", ".apks", ".apkm"}:
            return "application/zip"

        return "application/octet-stream"
    
    def _candidate_content_types_for(self, apk_path: Path) -> list[str | None]:
        suffix = apk_path.suffix.lower()

        if suffix == ".apk":
            return [
                "application/vnd.android.package-archive",
                "application/octet-stream",
                None,
            ]

        if suffix in {".xapk", ".apks", ".apkm"}:
            return [
                "application/octet-stream",
                None,
                "application/zip",
                "application/x-zip-compressed",
            ]

        return [
            "application/octet-stream",
            None,
        ]

    def _is_retryable_upload_error(self, response: requests.Response) -> bool:
        if response.status_code in {400, 415}:
            return "File format not Supported" in response.text or "Unsupported" in response.text

        return False



def check_mobsf_health() -> dict[str, Any]:
    return MobSFClient().check_health()