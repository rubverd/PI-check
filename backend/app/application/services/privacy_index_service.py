from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.application.services.mastg_catalog import RECOMMENDED_MASTG_TESTS, RECOMMENDED_PRIVACY_INDICES
from app.domain.entities.privacy_index import PrivacyIndex
from app.domain.entities.privacy_index_result import PrivacyIndexResult
from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.persistence.repositories.mastg_evaluation_repository import MastgEvaluationRepository
from app.infrastructure.persistence.repositories.mastg_test_repository import MastgTestRepository
from app.infrastructure.persistence.repositories.privacy_index_repository import PrivacyIndexRepository

logger = logging.getLogger("pi-check")


class PrivacyIndexService:
    def __init__(self, db: Session):
        self.db = db
        self.test_repository = MastgTestRepository(db)
        self.index_repository = PrivacyIndexRepository(db)
        self.evaluation_repository = MastgEvaluationRepository(db)

    def load_recommended_catalog(self) -> tuple[int, int, int]:
        created_tests = 0
        created_indices = 0
        created_links = 0

        for test in RECOMMENDED_MASTG_TESTS:
            if self.test_repository.find_by_id(test.id_mastg) is None:
                created_tests += 1
            self.test_repository.save(test)
            logger.info("[CATALOG] Prueba recomendada disponible: %s", test.id_mastg)

        for index in RECOMMENDED_PRIVACY_INDICES:
            if self.index_repository.find_by_id(index.id_indice) is None:
                created_indices += 1
            self.index_repository.save(
                PrivacyIndex(
                    id_indice=index.id_indice,
                    nombre=index.nombre,
                    descripcion=index.descripcion,
                    ruta_del_script=index.ruta_del_script,
                    pruebas_mastg=[],
                )
            )
            for id_mastg in index.pruebas_mastg or []:
                before = set(self.index_repository.list_test_ids(index.id_indice))
                self.index_repository.add_test(index.id_indice, id_mastg)
                after = set(self.index_repository.list_test_ids(index.id_indice))
                if id_mastg not in before and id_mastg in after:
                    created_links += 1
            logger.info("[CATALOG] Índice recomendado disponible: %s", index.id_indice)

        return created_tests, created_indices, created_links

    def calculate_index_result(
        self,
        id_indice: str,
        id_app: str,
        version: str,
    ) -> PrivacyIndexResult | None:
        index = self.index_repository.find_by_id(id_indice)
        if index is None:
            logger.info("[INDEX] Índice no configurado: %s", id_indice)
            return None

        logger.info("[INDEX] Calculando %s", id_indice)
        evaluations = {
            evaluation.id_mastg: evaluation
            for evaluation in self.evaluation_repository.find_by_version(id_app, version)
        }
        test_ids = index.pruebas_mastg or []
        relevant = [evaluations[test_id] for test_id in test_ids if test_id in evaluations]

        passed = sum(1 for item in relevant if item.resultado == MastgResultStatus.PASS)
        failed = sum(1 for item in relevant if item.resultado == MastgResultStatus.FAIL)
        errors = sum(1 for item in relevant if item.resultado == MastgResultStatus.ERROR)
        not_applicable = sum(
            1 for item in relevant if item.resultado == MastgResultStatus.NOT_APPLICABLE
        )
        total = len(relevant)

        result = PrivacyIndexResult(
            id_indice=index.id_indice,
            nombre_indice=index.nombre,
            pruebas_superadas=passed,
            pruebas_totales=total,
            pruebas_fallidas=failed,
            pruebas_error=errors,
            pruebas_no_aplicables=not_applicable,
        )

        logger.info(
            "[INDEX] Resultado: %s/%s = %.3f",
            result.pruebas_superadas,
            result.pruebas_totales,
            result.puntuacion,
        )
        return result
