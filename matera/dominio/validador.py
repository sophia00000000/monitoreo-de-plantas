"""Reglas de diagnostico: criterios por parametro, regla de agregacion y Evaluador (RF1-RF4, RF6)."""
from abc import ABC, abstractmethod
from math import isfinite

from matera.dominio.errores import (
    DatosInvalidos,
    EspecieDesconocida,
    ParametroAusente,
    ValorFueraDeRangoFisico,
    ValorNoNumerico,
)
from matera.dominio.modelo import (
    PARAMETROS,
    Diagnostico,
    Especie,
    EstadoGlobal,
    EstadoParametro,
    EvaluacionParametro,
    Lectura,
    Rango,
    normalizar_especie,
)
from matera.dominio.puertos.entrada import DiagnosticarPort
from matera.dominio.puertos.salida import ConsultarRangosPort


# ---------------------------------------------------------------- criterios

class Criterio(ABC):
    def __init__(self, rango: Rango):
        self.minimo = rango.minimo
        self.maximo = rango.maximo

    @abstractmethod
    def evaluar(self, valor: float) -> EstadoParametro:
        ...


class CriterioRango(Criterio):
    def evaluar(self, valor: float) -> EstadoParametro:
        if valor < self.minimo:
            return EstadoParametro.BAJO
        if valor > self.maximo:
            return EstadoParametro.ALTO
        return EstadoParametro.OPTIMO


class CriterioHumedad(CriterioRango):
    pass


class CriterioLuz(CriterioRango):
    pass


class CriterioTemperatura(CriterioRango):
    pass


class CriterioFactory:
    """Agregar un parametro (p. ej. pH) = registrar su clase aqui y su rango en PARAMETROS."""

    _tipos = {
        "humedad": CriterioHumedad,
        "luz": CriterioLuz,
        "temperatura": CriterioTemperatura,
    }

    def crear(self, parametro: str, rango: Rango) -> Criterio:
        clase = self._tipos.get(parametro)
        if clase is None:
            raise DatosInvalidos(f"Parametro no soportado: {parametro}", campo=parametro)
        return clase(rango)


class ReglaAgregacion:
    """0 parametros fuera de rango: SALUDABLE; 1: EN_RIESGO; 2 o mas: CRITICO (RF3)."""

    def estado_global(self, estados: list[EstadoParametro]) -> EstadoGlobal:
        fuera = sum(estado != EstadoParametro.OPTIMO for estado in estados)
        if fuera == 0:
            return EstadoGlobal.SALUDABLE
        if fuera == 1:
            return EstadoGlobal.EN_RIESGO
        return EstadoGlobal.CRITICO


# ---------------------------------------------------------------- validaciones

def validar_lectura(lectura: Lectura, parametros: list[str]) -> None:
    """Parametro ausente, valor no numerico y valor fuera del rango fisico (RF6)."""
    for codigo in parametros:
        if codigo not in lectura.valores:
            raise ParametroAusente(f"Falta el parametro: {codigo}.", campo=codigo)
        valor = lectura.valores[codigo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not isfinite(valor):
            raise ValorNoNumerico(f"El parametro {codigo} debe ser numerico.", campo=codigo)
        fisico = PARAMETROS.get(codigo)
        if fisico and not fisico.min_fisico <= valor <= fisico.max_fisico:
            raise ValorFueraDeRangoFisico(
                f"{fisico.etiqueta} debe estar entre {fisico.min_fisico} y {fisico.max_fisico} {fisico.unidad}.",
                campo=codigo,
            )


def validar_especie(especie: Especie) -> None:
    """Una especie del catalogo define rangos validos para todos los parametros conocidos."""
    if not especie.nombre:
        raise DatosInvalidos("La especie necesita un nombre.", campo="nombre")
    for codigo, parametro in PARAMETROS.items():
        rango = especie.rangos.get(codigo)
        if rango is None:
            raise ParametroAusente(f"Falta el rango de {codigo}.", campo=codigo)
        if rango.minimo < parametro.min_fisico or rango.maximo > parametro.max_fisico:
            raise ValorFueraDeRangoFisico(
                f"El rango de {codigo} debe estar entre {parametro.min_fisico} y {parametro.max_fisico}.",
                campo=codigo,
            )
    desconocidos = set(especie.rangos) - set(PARAMETROS)
    if desconocidos:
        raise DatosInvalidos(f"Parametros no soportados: {', '.join(sorted(desconocidos))}.")


# ---------------------------------------------------------------- caso de uso

class Evaluador(DiagnosticarPort):
    """Diagnostico ad hoc y diagnostico de cada lectura registrada."""

    def __init__(
        self,
        rangos: ConsultarRangosPort,
        criterios: CriterioFactory | None = None,
        regla: ReglaAgregacion | None = None,
    ):
        self._rangos = rangos
        self._criterios = criterios or CriterioFactory()
        self._regla = regla or ReglaAgregacion()

    def diagnosticar(self, especie: str, lectura: Lectura) -> Diagnostico:
        if not isinstance(especie, str) or not especie.strip():
            raise ParametroAusente("Falta el parametro: especie.", campo="especie")
        encontrada = self._rangos.obtener(normalizar_especie(especie))
        if encontrada is None or not encontrada.activa:
            raise EspecieDesconocida("La especie no esta soportada.", especie=especie)
        return self.evaluar(encontrada, lectura)

    def evaluar(self, especie: Especie, lectura: Lectura) -> Diagnostico:
        validar_lectura(lectura, list(especie.rangos))
        evaluaciones = []
        for codigo, rango in especie.rangos.items():
            valor = float(lectura.valores[codigo])
            estado = self._criterios.crear(codigo, rango).evaluar(valor)
            evaluaciones.append(EvaluacionParametro(
                parametro=codigo,
                valor=valor,
                unidad=PARAMETROS[codigo].unidad if codigo in PARAMETROS else "",
                minimo=rango.minimo,
                maximo=rango.maximo,
                estado=estado,
                recomendacion=self._recomendacion(codigo, estado, rango),
            ))
        return Diagnostico(
            especie=especie.nombre,
            estado_global=self._regla.estado_global([e.estado for e in evaluaciones]),
            parametros=tuple(evaluaciones),
        )

    @staticmethod
    def _recomendacion(codigo: str, estado: EstadoParametro, rango: Rango) -> str | None:
        if estado == EstadoParametro.OPTIMO:
            return None
        etiqueta = PARAMETROS[codigo].etiqueta if codigo in PARAMETROS else codigo.capitalize()
        limites = f"({rango.minimo:g}-{rango.maximo:g})"
        if estado == EstadoParametro.BAJO:
            return f"{etiqueta} esta por debajo del rango recomendado {limites}; aumente este parametro gradualmente."
        return f"{etiqueta} esta por encima del rango recomendado {limites}; reduzca este parametro gradualmente."
