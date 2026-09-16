from abc import ABC, abstractmethod

from modelos import CriterioConfig


class Criterio(ABC):
    def __init__(self, configuracion: CriterioConfig):
        self.minimo = configuracion.minimo
        self.maximo = configuracion.maximo

    @abstractmethod
    def evaluar(self, valor: float) -> str:
        pass


class CriterioRango(Criterio):
    def evaluar(self, valor: float) -> str:
        return "BUENO" if self.minimo <= valor <= self.maximo else "MALO"


class CriterioHumedad(CriterioRango):
    pass


class CriterioLuz(CriterioRango):
    pass


class CriterioTemp(CriterioRango):
    pass


class CriterioFactory:
    _tipos = {
        "humedad": CriterioHumedad,
        "iluminacion": CriterioLuz,
        "temperatura": CriterioTemp,
    }

    def crear(self, configuracion: CriterioConfig) -> Criterio:
        clase_criterio = self._tipos.get(configuracion.tipo)
        if clase_criterio is None:
            raise ValueError(f"Criterio no soportado: {configuracion.tipo}")
        return clase_criterio(configuracion)