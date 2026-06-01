from enum import Enum


class IntegrationModel(str, Enum):
    HEALTH_CONNECT = "HEALTH_CONNECT"
    LEGACY = "LEGACY"
    UNKNOWN = "UNKNOWN"