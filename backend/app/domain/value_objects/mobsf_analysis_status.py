from enum import Enum


class MobSFAnalysisStatus(str, Enum):
    NOT_ANALYZED = "NOT_ANALYZED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"