from dataclasses import dataclass
from typing import Any


@dataclass
class MobSFReport:
    hash_mobsf: str
    file_name: str | None
    scan_type: str | None
    ruta_informe: str | None
    json_report: dict[str, Any]