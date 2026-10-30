from datetime import datetime

from matera.dominio.errores import DatosInvalidos
from matera.dominio.modelo import Identidad, Medicion, PlantaDetalle
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.puertos.entrada import ConsultarPlantaPort
from matera.dominio.puertos.salida import (
    HistorialLecturasPort,
    RepositorioDispositivosPort,
    RepositorioPlantasPort,
)

LIMITE_HISTORIAL = 1000


class ConsultaPlantaService(ConsultarPlantaPort):
    def __init__(
        self,
        plantas: RepositorioPlantasPort,
        dispositivos: RepositorioDispositivosPort,
        historial: HistorialLecturasPort,
        politica: PoliticaPropiedad,
    ):
        self._plantas = plantas
        self._dispositivos = dispositivos
        self._historial = historial
        self._politica = politica

    def listar(self, identidad: Identidad) -> list[PlantaDetalle]:
        return [
            PlantaDetalle(
                planta=planta,
                vinculo=vinculo,
                dispositivo=self._dispositivos.por_planta(planta.id),
                ultima_medicion=self._historial.ultima(planta.id),
            )
            for planta, vinculo in self._plantas.listar_de_usuario(identidad.usuario_id)
            if planta.activa
        ]

    def detalle(self, identidad: Identidad, planta_id: int) -> PlantaDetalle:
        planta = self._politica.exigir_ver(identidad, planta_id)
        return PlantaDetalle(
            planta=planta,
            vinculo=self._plantas.vinculo(planta_id, identidad.usuario_id),
            dispositivo=self._dispositivos.por_planta(planta_id),
            ultima_medicion=self._historial.ultima(planta_id),
        )

    def historial(
        self,
        identidad: Identidad,
        planta_id: int,
        desde: datetime | None,
        hasta: datetime | None,
        limite: int,
    ) -> list[Medicion]:
        self._politica.exigir_ver(identidad, planta_id)
        if desde and hasta and desde > hasta:
            raise DatosInvalidos("La fecha 'desde' debe ser anterior a 'hasta'.", campo="desde")
        limite = max(1, min(limite, LIMITE_HISTORIAL))
        return self._historial.listar(planta_id, desde, hasta, limite)
