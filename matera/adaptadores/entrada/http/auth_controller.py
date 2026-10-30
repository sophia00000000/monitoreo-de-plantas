from flask import Blueprint, jsonify

from matera.adaptadores.entrada.http.comun import cuerpo_json, texto
from matera.adaptadores.entrada.http.limitador import LimitadorIntentos
from matera.adaptadores.serializacion import usuario_a_json
from matera.dominio.puertos.entrada import AutenticarUsuarioPort


def crear_auth_controller(autenticacion: AutenticarUsuarioPort, limitador: LimitadorIntentos) -> Blueprint:
    bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

    @bp.post("/registro")
    @limitador.limitar("registro")
    def registro():
        datos = cuerpo_json()
        usuario = autenticacion.registrar(
            texto(datos, "nombre"), texto(datos, "email"), texto(datos, "password")
        )
        return jsonify({"usuario": usuario_a_json(usuario)}), 201

    @bp.post("/login")
    @limitador.limitar("login")
    def login():
        datos = cuerpo_json()
        sesion = autenticacion.iniciar_sesion(texto(datos, "usuario"), texto(datos, "password"))
        return jsonify({"token": sesion.token, "usuario": usuario_a_json(sesion.usuario)})

    return bp
