from flask import Blueprint, g, jsonify, request

from matera.adaptadores.entrada.http.comun import cuerpo_json, leer_rangos, texto
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.serializacion import especie_a_json, solicitud_a_json
from matera.dominio.modelo import Especie
from matera.dominio.puertos.entrada import GestionarEspeciesPort


def crear_especies_controller(especies: GestionarEspeciesPort, verificador: JwtVerificador) -> Blueprint:
    bp = Blueprint("especies", __name__, url_prefix="/api/v1/especies")
    autenticado = verificador.requerido

    def especie_desde(datos: dict, nombre: str | None = None) -> Especie:
        return Especie(
            nombre=nombre or texto(datos, "nombre"),
            nombre_cientifico=texto(datos, "nombre_cientifico", requerido=False) or "",
            fuente=texto(datos, "fuente", requerido=False) or "admin",
            rangos=leer_rangos(datos),
        )

    @bp.post("/solicitudes")
    @autenticado
    def solicitar():
        datos = cuerpo_json()
        solicitud = especies.solicitar(
            g.identidad, texto(datos, "nombre"), texto(datos, "justificacion", requerido=False) or ""
        )
        return jsonify(solicitud_a_json(solicitud)), 201

    @bp.get("/solicitudes")
    @autenticado
    def listar_solicitudes():
        solicitudes = especies.listar_solicitudes(g.identidad, request.args.get("estado") or None)
        return jsonify({"solicitudes": [solicitud_a_json(s) for s in solicitudes]})

    @bp.post("/solicitudes/<int:solicitud_id>/aprobar")
    @autenticado
    def aprobar(solicitud_id: int):
        solicitud = especies.aprobar(g.identidad, solicitud_id, especie_desde(cuerpo_json()))
        return jsonify(solicitud_a_json(solicitud))

    @bp.post("/solicitudes/<int:solicitud_id>/rechazar")
    @autenticado
    def rechazar(solicitud_id: int):
        return jsonify(solicitud_a_json(especies.rechazar(g.identidad, solicitud_id)))

    @bp.put("/<nombre>")
    @autenticado
    def guardar(nombre: str):
        especie = especies.guardar_especie(g.identidad, especie_desde(cuerpo_json(), nombre))
        return jsonify(especie_a_json(especie))

    @bp.delete("/<nombre>")
    @autenticado
    def desactivar(nombre: str):
        especies.desactivar_especie(g.identidad, nombre)
        return "", 204

    return bp
