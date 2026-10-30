from matera.dominio.modelo import Especie
from matera.dominio.puertos.entrada import ConsultarCatalogoPort
from matera.dominio.puertos.salida import ConsultarRangosPort


class CatalogoService(ConsultarCatalogoPort):
    def __init__(self, rangos: ConsultarRangosPort):
        self._rangos = rangos

    def listar_especies(self) -> list[Especie]:
        return sorted(
            (especie for especie in self._rangos.listar() if especie.activa),
            key=lambda especie: especie.nombre,
        )
