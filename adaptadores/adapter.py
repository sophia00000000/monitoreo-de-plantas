from abc import ABC, abstractmethod


class Adapter(ABC):
    @abstractmethod
    def cargar_configuracion_criterios(self) -> list[dict]:
        pass