from flask import Blueprint, jsonify, request

from modelos import CondicionesAmbientales
from servicios.evaluador import Evaluador


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
            return jsonify({"error": "El cuerpo debe ser un JSON valido"}), 400

        try:
            especie = _texto_requerido(datos, "especie")
            valores = {
                _criterio_interno(criterio["nombre"]): _numero(
                    datos, _criterio_externo(criterio["nombre"])
                )
                for criterio in evaluador.listar_criterios(especie)
            }
            condiciones = CondicionesAmbientales(valores=valores)
            resultado = evaluador.evaluar_planta(especie, condiciones)
            return jsonify(resultado.a_dict())
        except KeyError as error:
            return jsonify({"error": f"Falta el campo: {error.args[0]}"}), 400
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    return blueprint


def _numero(datos: dict, campo: str) -> float:
    if campo not in datos or datos[campo] in (None, ""):
        raise ValueError(f"Falta el campo: {campo}")
    valor = datos[campo]
    if isinstance(valor, bool):
        raise ValueError(f"El campo {campo} debe ser numerico")
    numero = float(valor)
    if numero != numero:
        raise ValueError(f"El campo {campo} debe ser numerico")
    return numero


def _texto_requerido(datos: dict, campo: str) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Falta el campo: {campo}")
    return valor.strip()


def _criterio_externo(nombre: str) -> str:
    return "luz" if nombre == "iluminacion" else nombre


def _criterio_interno(nombre: str) -> str:
    return "iluminacion" if nombre == "iluminacion" else nombre
