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


@dataclass(frozen=True)
class Planta:
    nombre: str
    tipo: str
    criterios: Dict[str, CriterioConfig]


@dataclass(frozen=True)
class ResultadoEvaluacion:
    planta: str
    tipo: str
    estado_general: str
    criterios: Dict[str, Dict[str, float | str]]

    def a_dict(self) -> dict:
        return {
            "planta": self.planta,
            "tipo": self.tipo,
            "estado_general": self.estado_general,
            "criterios": self.criterios,
        }
