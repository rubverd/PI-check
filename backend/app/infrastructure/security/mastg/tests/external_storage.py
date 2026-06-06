from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


EXTERNAL_STORAGE_MARKERS = [
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
    "getExternalStorageDirectory",
    "getExternalFilesDir",
    "getExternalCacheDir",
    "Environment.getExternalStoragePublicDirectory",
]


class ExternalStorageTest:
    id_prueba = "MASTG-TEST-0202"
    referencia_mastg = "MASTG-TEST-0202"
    nombre = "External Storage Access"
    descripcion = "Detecta permisos o APIs asociadas a almacenamiento externo."
    owasp_category = "MASVS-STORAGE"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        matches = context.find_patterns(EXTERNAL_STORAGE_MARKERS, max_results=100)
        markers = sorted({match.value for match in matches})
        status = MastgResultStatus.FAIL if markers else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"markers": markers},
        )
