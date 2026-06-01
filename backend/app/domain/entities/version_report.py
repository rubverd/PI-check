from dataclasses import dataclass, field

from app.domain.entities.app_version import AppVersion
from app.domain.entities.mastg_evaluation import MastgEvaluation
from app.domain.entities.mobsf_report import MobSFReport
from app.domain.entities.privacy_index_result import PrivacyIndexResult


@dataclass
class VersionReport:
    version_app: AppVersion
    mobsf_report: MobSFReport | None = None
    resultados_mastg: list[MastgEvaluation] = field(default_factory=list)
    resultados_indices: list[PrivacyIndexResult] = field(default_factory=list)