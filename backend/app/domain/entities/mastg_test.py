from dataclasses import dataclass


@dataclass
class MastgTest:
    id_mastg: str
    nombre: str
    referencia_script_implementacion: str | None = None
    categoria_masvs: str | None = None
    perfil: str | None = None
    referencia_mastg: str | None = None
    descripcion: str | None = None
    owasp_category: str | None = None
