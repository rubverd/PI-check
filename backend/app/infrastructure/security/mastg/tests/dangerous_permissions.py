from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


DANGEROUS_PRIVACY_PERMISSIONS = [
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.GET_ACCOUNTS",
    "android.permission.READ_CALENDAR",
    "android.permission.WRITE_CALENDAR",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.READ_PHONE_STATE",
    "android.permission.CALL_PHONE",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.SEND_SMS",
    "android.permission.BODY_SENSORS",
    "android.permission.ACTIVITY_RECOGNITION",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
]


class DangerousPermissionsTest:
    id_prueba = "MASTG-TEST-0254"
    referencia_mastg = "MASTG-TEST-0254"
    nombre = "Dangerous App Permissions"
    descripcion = "Detecta permisos peligrosos declarados o presentes en el APK."
    owasp_category = "MASVS-PRIVACY"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        matches = context.find_patterns(DANGEROUS_PRIVACY_PERMISSIONS, max_results=100)
        permissions = sorted({match.value for match in matches})
        status = MastgResultStatus.FAIL if permissions else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"permissions": permissions},
        )
