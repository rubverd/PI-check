from dataclasses import dataclass

from app.domain.entities.app_version import AppVersion
from app.domain.entities.mastg_evaluation import MastgEvaluation
from app.domain.entities.privacy_index_result import PrivacyIndexResult


@dataclass
class VersionReport:
    version_app: AppVersion
    resultados_mastg: list[MastgEvaluation]
    resultados_indices: list[PrivacyIndexResult]