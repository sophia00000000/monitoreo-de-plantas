from flask import Blueprint, g, jsonify

from matera.adaptadores.entrada.http.comun import cuerpo_json
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.serializacion import usuario_a_json
from matera.dominio.errores import DatosInvalidos
from matera.dominio.modelo import Rol
from matera.dominio.puertos.entrada import GestionarCuentasPort


def crear_admin_controller(cuentas: GestionarCuentasPort, verificador: JwtVerificador) -> Blueprint:
    bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

    @bp.get("/usuarios")
    @verificador.requerido
    def listar():
        return jsonify({"usuarios": [usuario_a_json(u) for u in cuentas.listar(g.identidad)]})

    @bp.patch("/usuarios/<int:usuario_id>")
    @verificador.requerido
    def actualizar(usuario_id: int):
        datos = cuerpo_json()
        activo = datos.get("activo")
        if activo is not None and not isinstance(activo, bool):
            raise DatosInvalidos("El campo activo debe ser booleano.", campo="activo")
        rol = datos.get("rol")
        if rol is not None and rol not in Rol.__members__:
            raise DatosInvalidos("Rol no valido.", campo="rol")
        usuario = cuentas.actualizar(g.identidad, usuario_id, activo, Rol(rol) if rol else None)
        return jsonify(usuario_a_json(usuario))

    return bp
