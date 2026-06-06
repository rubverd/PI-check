from __future__ import annotations

import logging
from pathlib import Path

from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgLiteTest, MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext
from app.infrastructure.security.mastg.tests import (
    BackupConfigTest,
    CleartextTrafficTest,
    DangerousPermissionsTest,
    ExternalStorageTest,
    HardcodedHttpUrlsTest,
    LoggingApisTest,
    UserCaTrustTest,
)

logger = logging.getLogger("pi-check")


AVAILABLE_TESTS: dict[str, MastgLiteTest] = {
    test.id_prueba: test
    for test in [
        DangerousPermissionsTest(),
        BackupConfigTest(),
        CleartextTrafficTest(),
        UserCaTrustTest(),
        HardcodedHttpUrlsTest(),
        ExternalStorageTest(),
        LoggingApisTest(),
    ]
}


class MastgLiteRunner:
    def __init__(self, tests: dict[str, MastgLiteTest] | None = None):
        self.tests = tests or AVAILABLE_TESTS

    def run_tests(
        self,
        artifact_path: Path,
        id_app: str,
        version: str,
        test_ids: list[str],
    ) -> list[MastgTestRunResult]:
        context = MastgAnalysisContext(
            artifact_path=artifact_path,
            id_app=id_app,
            version=version,
        )
        results: list[MastgTestRunResult] = []

        for test_id in test_ids:
            test = self.tests.get(test_id)
            if test is None:
                logger.info("[MASTG] Prueba %s sin implementación local; se omite", test_id)
                results.append(
                    MastgTestRunResult(
                        id_mastg=test_id,
                        status=MastgResultStatus.NOT_APPLICABLE,
                        evidence={"reason": "No existe implementación MASTG-lite local."},
                    )
                )
                continue

            logger.info("[MASTG] Ejecutando %s %s", test.id_prueba, test.nombre)
            try:
                result = test.run(context)
            except Exception as exc:
                logger.exception("[MASTG] Error ejecutando %s", test_id)
                result = MastgTestRunResult(
                    id_mastg=test_id,
                    status=MastgResultStatus.ERROR,
                    evidence={"error": str(exc)},
                    message=str(exc),
                )

            logger.info("[MASTG] Resultado %s: %s", test_id, result.status.value)
            results.append(result)

        return results
