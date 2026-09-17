from modelos import CondicionesAmbientales, ResultadoEvaluacion
from dominio.puertos import RepositorioPlantas
from servicios.criterios import CriterioFactory


class Evaluador:
    """Caso de uso: evalua las condiciones contra la configuracion de una planta."""

    def __init__(self, repository: RepositorioPlantas, criterio_factory: CriterioFactory):
        self._repository = repository
        self._criterio_factory = criterio_factory

    def listar_tipos(self) -> list[str]:
        return self._repository.listar_tipos()

    def listar_criterios(self, tipo: str) -> list[dict]:
        planta = self._repository.obtener_por_tipo(tipo)
        if planta is None:
            raise ValueError(f"Tipo de planta no soportado: {tipo}")
        return [
            {"nombre": nombre, "unidad": config.unidad}
            for nombre, config in planta.criterios.items()
        ]

    def evaluar_planta(
        self, tipo: str, condiciones: CondicionesAmbientales
    ) -> ResultadoEvaluacion:
        planta = self._repository.obtener_por_tipo(tipo)
        if planta is None:
            raise ValueError(f"Tipo de planta no soportado: {tipo}")

        criterios = {}
        recomendaciones = []
        for nombre, config in planta.criterios.items():
            if nombre not in condiciones.valores:
                raise ValueError(f"Falta la condicion: {nombre}")
            valor = condiciones.valores[nombre]
            criterio = self._criterio_factory.crear(config)
            estado = criterio.evaluar(valor)
            criterios[nombre] = {
                "valor": valor,
                "minimo": config.minimo,
                "maximo": config.maximo,
                "unidad": config.unidad,
                "estado": estado,
            }
            if estado != "OPTIMO":
                recomendaciones.append(
                    self._recomendacion(nombre, estado, config.minimo, config.maximo)
                )

        fuera_de_rango = sum(item["estado"] != "OPTIMO" for item in criterios.values())
        indice_vitalidad = (
            "SALUDABLE" if fuera_de_rango == 0
            else "EN_RIESGO" if fuera_de_rango == 1
            else "CRITICO"
        )
        return ResultadoEvaluacion(
            planta=planta.nombre,
            tipo=planta.tipo,
            indice_vitalidad=indice_vitalidad,
            criterios=criterios,
            recomendaciones=recomendaciones,
        )

    @staticmethod
    def _recomendacion(nombre: str, estado: str, minimo: float, maximo: float) -> str:
        etiquetas = {"humedad": "La humedad", "iluminacion": "La iluminacion", "temperatura": "La temperatura"}
        etiqueta = etiquetas.get(nombre, nombre.capitalize())
        if estado == "BAJO":
            return f"{etiqueta} esta por debajo del rango recomendado ({minimo}-{maximo}); aumente este parametro gradualmente."
        return f"{etiqueta} esta por encima del rango recomendado ({minimo}-{maximo}); reduzca este parametro gradualmente."
