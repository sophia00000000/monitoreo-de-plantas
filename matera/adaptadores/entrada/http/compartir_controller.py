from flask import Blueprint, g, jsonify

from matera.adaptadores.entrada.http.comun import cuerpo_json, texto
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.entrada.http.limitador import LimitadorIntentos
from matera.adaptadores.serializacion import fecha, planta_a_json
from matera.dominio.puertos.entrada import CompartirPlantaPort


def crear_compartir_controller(
    compartir: CompartirPlantaPort,
    verificador: JwtVerificador,
    limitador: LimitadorIntentos,
) -> Blueprint:
    bp = Blueprint("compartir", __name__, url_prefix="/api/v1")

    @bp.post("/plantas/<int:planta_id>/invitaciones")
    @verificador.requerido
    def generar(planta_id: int):
        invitacion = compartir.generar_invitacion(g.identidad, planta_id)
        # El backend devuelve el token en JSON; dibujar el QR es trabajo del front (RA1).
        return jsonify({
            "token": invitacion.token,
            "planta_id": invitacion.planta_id,
            "expira_en": fecha(invitacion.expira_en),
        }), 201

    @bp.post("/invitaciones/canje")
    @limitador.limitar("canje")
    @verificador.requerido
    def canjear():
        planta = compartir.canjear(g.identidad, texto(cuerpo_json(), "token"))
        return jsonify(planta_a_json(planta))

    return bp
