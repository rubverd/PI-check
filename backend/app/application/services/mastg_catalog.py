from app.domain.entities.mastg_test import MastgTest
from app.domain.entities.privacy_index import PrivacyIndex

RECOMMENDED_MASTG_TESTS: list[MastgTest] = [
    MastgTest("MASTG-TEST-0254", "Dangerous App Permissions", "mastg-lite:dangerous_permissions", "MASVS-PRIVACY", "STATIC", "MASTG-TEST-0254", "Detecta permisos peligrosos relevantes para privacidad.", "MASVS-PRIVACY"),
    MastgTest("MASTG-TEST-0262", "Backup Configurations Not Excluding Sensitive Data", "mastg-lite:backup_config", "MASVS-STORAGE", "STATIC", "MASTG-TEST-0262", "Busca configuraciones de backup no restrictivas.", "MASVS-STORAGE"),
    MastgTest("MASTG-TEST-0235", "Cleartext Traffic", "mastg-lite:cleartext_traffic", "MASVS-NETWORK", "STATIC", "MASTG-TEST-0235", "Detecta tráfico en claro permitido explícitamente.", "MASVS-NETWORK"),
    MastgTest("MASTG-TEST-0286", "Trust in User-Provided CAs", "mastg-lite:user_ca_trust", "MASVS-NETWORK", "STATIC", "MASTG-TEST-0286", "Detecta confianza en CAs instaladas por el usuario.", "MASVS-NETWORK"),
    MastgTest("MASTG-TEST-0233", "Hardcoded HTTP URLs", "mastg-lite:hardcoded_http_urls", "MASVS-NETWORK", "STATIC", "MASTG-TEST-0233", "Busca URLs http:// hardcodeadas.", "MASVS-NETWORK"),
    MastgTest("MASTG-TEST-0202", "External Storage Access", "mastg-lite:external_storage", "MASVS-STORAGE", "STATIC", "MASTG-TEST-0202", "Detecta permisos o APIs de almacenamiento externo.", "MASVS-STORAGE"),
    MastgTest("MASTG-TEST-0231", "Logging APIs", "mastg-lite:logging_apis", "MASVS-CODE", "STATIC", "MASTG-TEST-0231", "Detecta referencias a APIs de logging.", "MASVS-CODE"),
]

GLOBAL_INDEX_ID = "PI-INDEX-GLOBAL-LITE"

RECOMMENDED_PRIVACY_INDICES: list[PrivacyIndex] = [
    PrivacyIndex(GLOBAL_INDEX_ID, "Índice global MASTG-lite", "Agrupa las siete pruebas MASTG-lite iniciales.", None, [test.id_mastg for test in RECOMMENDED_MASTG_TESTS]),
    PrivacyIndex("PI-INDEX-DATA-EXPOSURE", "Índice de exposición de datos", "Agrupa señales de permisos, backup, almacenamiento externo y logging.", None, ["MASTG-TEST-0254", "MASTG-TEST-0262", "MASTG-TEST-0202", "MASTG-TEST-0231"]),
    PrivacyIndex("PI-INDEX-NETWORK-SECURITY", "Índice de seguridad de red", "Agrupa permisos transversales y señales de seguridad de red.", None, ["MASTG-TEST-0254", "MASTG-TEST-0235", "MASTG-TEST-0286", "MASTG-TEST-0233"]),
]
