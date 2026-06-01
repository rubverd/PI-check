from dataclasses import dataclass


@dataclass
class PrivacyIndex:
    id_indice: str
    nombre: str
    descripcion: str | None = None
    ruta_del_script: str | None = None
    pruebas_mastg: list[str] | None = None