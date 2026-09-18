from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CondicionesAmbientales:
    valores: Dict[str, float]


@dataclass(frozen=True)
class CriterioConfig:
    tipo: str
    minimo: float
    maximo: float
    unidad: str


@dataclass(frozen=True)
class Planta:
    nombre: str
    especie: str
    criterios: Dict[str, CriterioConfig]


@dataclass(frozen=True)
class ResultadoEvaluacion:
    planta: str
    especie: str
    indice_vitalidad: str
    criterios: Dict[str, Dict[str, float | str]]
    recomendaciones: list[str]

    def a_dict(self) -> dict:
        return {
            "planta": self.planta,
            "especie": self.especie,
            "indice_vitalidad": self.indice_vitalidad,
            "criterios": self.criterios,
            "recomendaciones": self.recomendaciones,
        }
