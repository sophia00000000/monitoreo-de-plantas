from math import isfinite

from flask import Blueprint, jsonify, request

from modelos import CondicionesAmbientales
from servicios.evaluador import Evaluador


class ParametroInvalido(ValueError):
    def __init__(self, campo: str, mensaje: str):
        super().__init__(mensaje)
        self.campo = campo


def crear_blueprint(evaluador: Evaluador) -> Blueprint:
    blueprint = Blueprint("plantas", __name__, url_prefix="/api")

    @blueprint.get("/plantas")
    def listar_plantas():
        especies = evaluador.listar_tipos()
        return jsonify({
            "plantas": [
                {"especie": especie, "criterios": evaluador.listar_criterios(especie)}
                for especie in especies
            ]
        })

    @blueprint.post("/evaluar")
    def evaluar():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return _error(
                "SOLICITUD_INVALIDA",
                "El cuerpo debe ser un objeto JSON valido.",
            )

        try:
            especie = _texto_requerido(datos, "especie")
            try:
                configuracion = evaluador.listar_criterios(especie)
            except ValueError:
                return _error(
                    "ESPECIE_NO_SOPORTADA",
                    "La especie no esta soportada.",
                    404,
                    {"especie": especie},
                )
            valores = {
                criterio["nombre"]: _numero(datos, criterio["nombre"])
                for criterio in configuracion
            }
            condiciones = CondicionesAmbientales(valores=valores)
            resultado = evaluador.evaluar_planta(especie, condiciones)
            return jsonify(resultado.a_dict())
        except KeyError as error:
            return _error(
                "PARAMETRO_INVALIDO",
                f"Falta el campo: {error.args[0]}.",
                detalle={"campo": error.args[0]},
            )
        except ParametroInvalido as error:
            return _error(
                "PARAMETRO_INVALIDO",
                str(error),
                detalle={"campo": error.campo},
            )
        except (TypeError, ValueError) as error:
            return _error("PARAMETRO_INVALIDO", str(error))

    return blueprint


def _numero(datos: dict, campo: str) -> float:
    if campo not in datos or datos[campo] in (None, ""):
        raise ParametroInvalido(campo, f"Falta el campo: {campo}.")
    valor = datos[campo]
    if isinstance(valor, bool):
        raise ParametroInvalido(campo, f"El campo {campo} debe ser numerico.")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ParametroInvalido(campo, f"El campo {campo} debe ser numerico.") from None
    if not isfinite(numero):
        raise ParametroInvalido(campo, f"El campo {campo} debe ser un numero finito.")
    limites = {
        "humedad": (0, 100),
        "iluminacion": (0, None),
        "temperatura": (-50, 60),
    }
    minimo, maximo = limites.get(campo, (None, None))
    fuera_de_limite = (
        (minimo is not None and numero < minimo)
        or (maximo is not None and numero > maximo)
    )
    if fuera_de_limite:
        limite = f"entre {minimo} y {maximo}" if maximo is not None else f"mayor o igual a {minimo}"
        raise ParametroInvalido(campo, f"El campo {campo} debe estar {limite}.")
    return numero


def _texto_requerido(datos: dict, campo: str) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ParametroInvalido(campo, f"Falta el campo: {campo}.")
    return valor.strip()


def _error(codigo: str, mensaje: str, status: int = 400, detalle: dict | None = None):
    return jsonify({
        "error": codigo,
        "mensaje": mensaje,
        "detalle": detalle or {},
    }), status
