from app.infrastructure.security.mastg.tests.backup_config import BackupConfigTest
from app.infrastructure.security.mastg.tests.cleartext_traffic import CleartextTrafficTest
from app.infrastructure.security.mastg.tests.dangerous_permissions import DangerousPermissionsTest
from app.infrastructure.security.mastg.tests.external_storage import ExternalStorageTest
from app.infrastructure.security.mastg.tests.hardcoded_http_urls import HardcodedHttpUrlsTest
from app.infrastructure.security.mastg.tests.logging_apis import LoggingApisTest
from app.infrastructure.security.mastg.tests.user_ca_trust import UserCaTrustTest

__all__ = [
    "BackupConfigTest",
    "CleartextTrafficTest",
    "DangerousPermissionsTest",
    "ExternalStorageTest",
    "HardcodedHttpUrlsTest",
    "LoggingApisTest",
    "UserCaTrustTest",
]
