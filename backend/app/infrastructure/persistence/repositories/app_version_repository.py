from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.app_version import AppVersion
from app.domain.value_objects.integration_model import IntegrationModel
from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus
from app.infrastructure.persistence.models.app_version_model import AppVersionModel


class AppVersionRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, id_app: str, version: str) -> AppVersion | None:
        model = self.db.get(AppVersionModel, (id_app, version))

        if model is None:
            return None

        return self._to_domain(model)

    def find_versions_by_app_id(self, id_app: str) -> list[AppVersion]:
        stmt = (
            select(AppVersionModel)
            .where(AppVersionModel.id_app == id_app)
            .order_by(
                AppVersionModel.fecha_version.desc().nullslast(),
                AppVersionModel.version_code.desc().nullslast(),
                AppVersionModel.version.desc(),
            )
        )

        models = self.db.execute(stmt).scalars().all()

        return [self._to_domain(model) for model in models]

    def find_latest_by_app_id(self, id_app: str) -> AppVersion | None:
        stmt = (
            select(AppVersionModel)
            .where(AppVersionModel.id_app == id_app)
            .order_by(
                AppVersionModel.fecha_version.desc().nullslast(),
                AppVersionModel.version_code.desc().nullslast(),
                AppVersionModel.version.desc(),
            )
            .limit(1)
        )

        model = self.db.execute(stmt).scalars().first()

        if model is None:
            return None

        return self._to_domain(model)

    def find_by_apk_sha256(
        self,
        id_app: str,
        apk_sha256: str,
    ) -> AppVersion | None:
        stmt = (
            select(AppVersionModel)
            .where(AppVersionModel.id_app == id_app)
            .where(AppVersionModel.apk_sha256 == apk_sha256)
            .limit(1)
        )

        model = self.db.execute(stmt).scalars().first()

        if model is None:
            return None

        return self._to_domain(model)

    def find_latest_with_mobsf_report(self, id_app: str) -> AppVersion | None:
        stmt = (
            select(AppVersionModel)
            .where(AppVersionModel.id_app == id_app)
            .where(AppVersionModel.estado_mobsf == MobSFAnalysisStatus.SUCCESS.value)
            .where(AppVersionModel.ruta_informe_mobsf.is_not(None))
            .where(AppVersionModel.hash_mobsf.is_not(None))
            .order_by(
                AppVersionModel.fecha_version.desc().nullslast(),
                AppVersionModel.version_code.desc().nullslast(),
                AppVersionModel.version.desc(),
            )
            .limit(1)
        )

        model = self.db.execute(stmt).scalars().first()

        if model is None:
            return None

        return self._to_domain(model)

    def save(self, app_version: AppVersion) -> AppVersion:
        existing = self.db.get(
            AppVersionModel,
            (app_version.id_app, app_version.version),
        )

        if existing is None:
            model = self._to_model(app_version)
            self.db.add(model)
            self.db.flush()
            return self._to_domain(model)

        existing.version_code = app_version.version_code
        existing.fecha_version = app_version.fecha_version
        existing.categoria = app_version.categoria
        existing.modelo_integracion = app_version.modelo_integracion.value
        existing.ruta_informe_mobsf = app_version.ruta_informe_mobsf
        existing.hash_mobsf = app_version.hash_mobsf
        existing.apk_sha256 = app_version.apk_sha256
        existing.ruta_apk = app_version.ruta_apk
        existing.estado_mobsf = app_version.estado_mobsf.value

        self.db.flush()

        return self._to_domain(existing)

    def update_mobsf_report(
        self,
        id_app: str,
        version: str,
        hash_mobsf: str | None,
        ruta_informe_mobsf: str | None,
        estado_mobsf: MobSFAnalysisStatus,
    ) -> AppVersion:
        model = self.db.get(AppVersionModel, (id_app, version))

        if model is None:
            raise ValueError(
                f"No existe VERSION_APP para id_app={id_app}, version={version}"
            )

        model.hash_mobsf = hash_mobsf
        model.ruta_informe_mobsf = ruta_informe_mobsf
        model.estado_mobsf = estado_mobsf.value

        self.db.flush()

        return self._to_domain(model)

    def _to_domain(self, model: AppVersionModel) -> AppVersion:
        return AppVersion(
            id_app=model.id_app,
            version=model.version,
            version_code=model.version_code,
            fecha_version=model.fecha_version,
            categoria=model.categoria,
            modelo_integracion=IntegrationModel(model.modelo_integracion),
            ruta_informe_mobsf=model.ruta_informe_mobsf,
            hash_mobsf=model.hash_mobsf,
            apk_sha256=model.apk_sha256,
            ruta_apk=model.ruta_apk,
            estado_mobsf=MobSFAnalysisStatus(model.estado_mobsf),
        )

    def _to_model(self, app_version: AppVersion) -> AppVersionModel:
        return AppVersionModel(
            id_app=app_version.id_app,
            version=app_version.version,
            version_code=app_version.version_code,
            fecha_version=app_version.fecha_version,
            categoria=app_version.categoria,
            modelo_integracion=app_version.modelo_integracion.value,
            ruta_informe_mobsf=app_version.ruta_informe_mobsf,
            hash_mobsf=app_version.hash_mobsf,
            apk_sha256=app_version.apk_sha256,
            ruta_apk=app_version.ruta_apk,
            estado_mobsf=app_version.estado_mobsf.value,
        )
