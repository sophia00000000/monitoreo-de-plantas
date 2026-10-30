from flask import Blueprint, jsonify

from matera.adaptadores.serializacion import especie_a_json
from matera.dominio.puertos.entrada import ConsultarCatalogoPort


def crear_catalogo_controller(catalogo: ConsultarCatalogoPort) -> Blueprint:
    bp = Blueprint("catalogo", __name__, url_prefix="/api/v1")

    @bp.get("/especies")
    def listar_especies():
        return jsonify({"especies": [especie_a_json(e) for e in catalogo.listar_especies()]})

    return bp
