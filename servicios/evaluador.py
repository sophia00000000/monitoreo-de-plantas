from modelos import CondicionesAmbientales, ResultadoEvaluacion
from servicios.criterios import CriterioFactory
from repositorios.planta_repository import PlantaRepository


class Evaluador:
    """Caso de uso: evalua las condiciones contra la configuracion de una planta."""

    def __init__(self, repository: PlantaRepository, criterio_factory: CriterioFactory):
        self._repository = repository
        self._criterio_factory = criterio_factory

    def listar_tipos(self) -> list[str]:
        return self._repository.listar_tipos()

    def listar_criterios(self, tipo: str) -> list[str]:
        planta = self._repository.obtener_por_tipo(tipo)
        if planta is None:
            raise ValueError(f"Tipo de planta no soportado: {tipo}")
        return list(planta.criterios)

    def evaluar_planta(
        self, tipo: str, condiciones: CondicionesAmbientales
    ) -> ResultadoEvaluacion:
        planta = self._repository.obtener_por_tipo(tipo)
        if planta is None:
            raise ValueError(f"Tipo de planta no soportado: {tipo}")

        criterios = {}
        for nombre, config in planta.criterios.items():
            if nombre not in condiciones.valores:
                raise ValueError(f"Falta la condicion: {nombre}")
            valor = condiciones.valores[nombre]
            criterio = self._criterio_factory.crear(config)
            config = planta.criterios[nombre]
            criterios[nombre] = {
                "valor": valor,
                "minimo": config.minimo,
                "maximo": config.maximo,
                "estado": criterio.evaluar(valor),
            }

        estado_general = (
            "BUENO"
            if all(item["estado"] == "BUENO" for item in criterios.values())
            else "MAL ESTADO"
        )
        return ResultadoEvaluacion(
            planta=planta.nombre,
            tipo=planta.tipo,
            estado_general=estado_general,
            criterios=criterios,
        )
