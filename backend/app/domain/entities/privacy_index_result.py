from dataclasses import dataclass


@dataclass
class PrivacyIndexResult:
    id_indice: str
    nombre_indice: str

    pruebas_superadas: int
    pruebas_totales: int
    pruebas_fallidas: int = 0
    pruebas_error: int = 0
    pruebas_no_aplicables: int = 0

    @property
    def puntuacion(self) -> float:
        if self.pruebas_totales == 0:
            return 0.0

        return self.pruebas_superadas / self.pruebas_totales