from abc import ABC, abstractmethod
from typing import Protocol


class FuenteConfiguracionPlantas(ABC):
    """Puerto del dominio para obtener rangos de especies."""

    @abstractmethod
    def cargar_configuracion_criterios(self) -> list[dict]:
        pass


class RepositorioPlantas(Protocol):
    """Puerto que necesita la aplicacion para consultar especies."""

    def obtener_por_especie(self, especie: str):
        ...

    def listar_especies(self) -> list[str]:
        ...
