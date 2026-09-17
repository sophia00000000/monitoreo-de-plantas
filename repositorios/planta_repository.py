from adaptadores.adapter import Adapter
from modelos import CriterioConfig, Planta


class PlantaRepository:
    """Fuente de datos de las plantas y sus rangos ambientales."""

    def __init__(self, adapter: Adapter):
        self._plantas = self._cargar_plantas(adapter)

    def _cargar_plantas(self, adapter: Adapter) -> dict[str, Planta]:
        plantas = {}
        for datos in adapter.cargar_configuracion_criterios():
            criterios = {
                criterio["nombre"]: CriterioConfig(
                    tipo=criterio["nombre"],
                    minimo=criterio["minimo"],
                    maximo=criterio["maximo"],
                    unidad=criterio["unidad"],
                )
                for criterio in datos["criterios"]
            }
            planta = Planta(datos["nombre"], datos["tipo"], criterios)
            plantas[planta.tipo] = planta
        return plantas

    def obtener_por_tipo(self, tipo: str) -> Planta | None:
        return self._plantas.get(tipo.strip().lower())

    def listar_tipos(self) -> list[str]:
        return list(self._plantas.keys())
