from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.mastg_evaluation import MastgEvaluation
from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.persistence.models.mastg_evaluation_model import MastgEvaluationModel


class MastgEvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, id_app: str, version: str, id_mastg: str) -> MastgEvaluation | None:
        model = self.db.get(MastgEvaluationModel, (id_app, version, id_mastg))
        return self._to_domain(model) if model else None

    def find_by_version(self, id_app: str, version: str) -> list[MastgEvaluation]:
        stmt = (
            select(MastgEvaluationModel)
            .where(MastgEvaluationModel.id_app == id_app)
            .where(MastgEvaluationModel.version == version)
            .order_by(MastgEvaluationModel.id_mastg.asc())
        )
        return [self._to_domain(model) for model in self.db.execute(stmt).scalars().all()]

    def save(self, evaluation: MastgEvaluation) -> MastgEvaluation:
        existing = self.db.get(
            MastgEvaluationModel,
            (evaluation.id_app, evaluation.version, evaluation.id_mastg),
        )
        if existing is None:
            model = self._to_model(evaluation)
            self.db.add(model)
            self.db.flush()
            return self._to_domain(model)

        existing.resultado = evaluation.resultado.value
        existing.ruta_resultado_json = evaluation.ruta_resultado_json
        existing.mensaje_error = evaluation.mensaje_error
        existing.fecha_ejecucion = evaluation.fecha_ejecucion
        self.db.flush()
        return self._to_domain(existing)

    def _to_domain(self, model: MastgEvaluationModel) -> MastgEvaluation:
        return MastgEvaluation(
            id_app=model.id_app,
            version=model.version,
            id_mastg=model.id_mastg,
            resultado=MastgResultStatus(model.resultado),
            ruta_resultado_json=model.ruta_resultado_json,
            mensaje_error=model.mensaje_error,
            fecha_ejecucion=model.fecha_ejecucion,
        )

    def _to_model(self, evaluation: MastgEvaluation) -> MastgEvaluationModel:
        return MastgEvaluationModel(
            id_app=evaluation.id_app,
            version=evaluation.version,
            id_mastg=evaluation.id_mastg,
            resultado=evaluation.resultado.value,
            ruta_resultado_json=evaluation.ruta_resultado_json,
            mensaje_error=evaluation.mensaje_error,
            fecha_ejecucion=evaluation.fecha_ejecucion,
        )
