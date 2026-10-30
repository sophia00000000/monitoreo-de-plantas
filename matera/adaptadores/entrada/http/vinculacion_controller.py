from flask import Blueprint, g, jsonify

from matera.adaptadores.entrada.http.comun import cuerpo_json, texto
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.entrada.http.limitador import LimitadorIntentos
from matera.adaptadores.serializacion import dispositivo_a_json
from matera.dominio.puertos.entrada import VincularDispositivoPort


def crear_vinculacion_controller(
    vincular: VincularDispositivoPort,
    verificador: JwtVerificador,
    limitador: LimitadorIntentos,
) -> Blueprint:
    bp = Blueprint("vinculacion", __name__, url_prefix="/api/v1")

    @bp.post("/plantas/<int:planta_id>/dispositivo")
    @limitador.limitar("vinculacion")
    @verificador.requerido
    def vincular_dispositivo(planta_id: int):
        datos = cuerpo_json()
        dispositivo = vincular.vincular(g.identidad, planta_id, texto(datos, "mac"))
        return jsonify(dispositivo_a_json(dispositivo)), 201

    @bp.delete("/plantas/<int:planta_id>/dispositivo")
    @verificador.requerido
    def desvincular_dispositivo(planta_id: int):
        vincular.desvincular(g.identidad, planta_id)
        return "", 204

    return bp
