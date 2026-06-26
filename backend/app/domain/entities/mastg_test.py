from dataclasses import dataclass


@dataclass
class MastgTest:
    id_mastg: str
    nombre: str
    referencia_script_implementacion: str | None = None
    categoria_masvs: str | None = None
    perfil: str | None = None
    descripcion: str | None = None
    origen: str | None = None
    tipo_relacion: str | None = None