from dominio.puertos import FuenteConfiguracionPlantas
from modelos import CriterioConfig, Planta


class PlantaRepository:
    """Fuente de datos de las plantas y sus rangos ambientales."""

    def __init__(self, adapter: FuenteConfiguracionPlantas):
        self._plantas = self._cargar_plantas(adapter)

    def _cargar_plantas(self, adapter: FuenteConfiguracionPlantas) -> dict[str, Planta]:
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
            planta = Planta(datos["nombre"], datos["especie"], criterios)
            plantas[planta.especie] = planta
        return plantas

    def obtener_por_especie(self, especie: str) -> Planta | None:
        return self._plantas.get(especie.strip().lower())

    def listar_especies(self) -> list[str]:
        return list(self._plantas.keys())
