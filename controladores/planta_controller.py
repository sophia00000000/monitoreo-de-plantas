from flask import Blueprint, jsonify, request

from modelos import CondicionesAmbientales
from servicios.evaluador import Evaluador


def crear_blueprint(evaluador: Evaluador) -> Blueprint:
    blueprint = Blueprint("plantas", __name__, url_prefix="/api")

    @blueprint.get("/plantas")
    def listar_plantas():
        tipos = evaluador.listar_tipos()
        return jsonify({
            "plantas": [
                {"tipo": tipo, "criterios": evaluador.listar_criterios(tipo)}
                for tipo in tipos
            ]
        })

    @blueprint.post("/evaluar")
    def evaluar():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify({"error": "El cuerpo debe ser un JSON valido"}), 400

        try:
            tipo = str(datos["tipo"])
            valores = {
                nombre: _numero(datos, nombre)
                for nombre in evaluador.listar_criterios(tipo)
            }
            condiciones = CondicionesAmbientales(valores=valores)
            resultado = evaluador.evaluar_planta(tipo, condiciones)
            return jsonify(resultado.a_dict())
        except KeyError as error:
            return jsonify({"error": f"Falta el campo: {error.args[0]}"}), 400
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    return blueprint


def _numero(datos: dict, campo: str) -> float:
    valor = datos[campo]
    numero = float(valor)
    if numero != numero:
        raise ValueError(f"El campo {campo} debe ser numerico")
    return numero
