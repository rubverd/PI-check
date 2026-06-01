from dataclasses import dataclass

from app.domain.entities.version_report import VersionReport


@dataclass
class ComparisonResult:
    app_a: VersionReport
    app_b: VersionReport
    id_indice_aplicado: str | None = None