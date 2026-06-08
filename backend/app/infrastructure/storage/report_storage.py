import json
import os
import re
from pathlib import Path
from typing import Any


class ReportStorage:
    def __init__(self, mobsf_reports_dir: str | None = None):
        self.mobsf_reports_dir = Path(
            mobsf_reports_dir
            or os.getenv("MOBSF_REPORTS_DIR", "/app/artifacts/reports/mobsf")
        )

    def save_mobsf_report(
        self,
        id_app: str,
        version: str,
        report_data: dict[str, Any],
    ) -> str:
        report_path = self.mobsf_report_path(id_app=id_app, version=version)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with report_path.open("w", encoding="utf-8") as file:
            json.dump(
                report_data,
                file,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        return str(report_path)

    def mobsf_report_path(self, id_app: str, version: str) -> Path:
        return (
            self.mobsf_reports_dir
            / self._safe_path_part(id_app)
            / self._safe_path_part(version)
            / "mobsf_report.json"
        )

    def load_mobsf_report(self, report_path: str | None) -> dict[str, Any] | None:
        if not report_path:
            return None

        path = Path(report_path)

        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _safe_path_part(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
        return cleaned or "unknown"
