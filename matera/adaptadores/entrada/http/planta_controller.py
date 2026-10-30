from flask import Blueprint, g, jsonify, request

from matera.adaptadores.entrada.http.comun import (
    cuerpo_json,
    entero,
    leer_fecha,
    leer_lectura,
    texto,
)
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.serializacion import (
    diagnostico_a_json,
    medicion_a_json,
    planta_a_json,
    planta_detalle_a_json,
)
from matera.dominio.puertos.entrada import (
    ConsultarPlantaPort,
    DiagnosticarPort,
    GestionarPlantasPort,
)


def crear_planta_controller(
    diagnosticar: DiagnosticarPort,
    gestionar: GestionarPlantasPort,
    consultar: ConsultarPlantaPort,
    verificador: JwtVerificador,
) -> Blueprint:
    bp = Blueprint("plantas", __name__, url_prefix="/api/v1")
    autenticado = verificador.requerido

    # ------------------------------------------------ diagnostico ad hoc: anonimo, no persiste (RF7)

    @bp.post("/diagnosticos")
    def diagnosticar_ad_hoc():
        datos = cuerpo_json()
        diagnostico = diagnosticar.diagnosticar(texto(datos, "especie"), leer_lectura(datos))
        return jsonify(diagnostico_a_json(diagnostico))

    # ------------------------------------------------ plantas del usuario (RF10, RF13, RF14)

    @bp.get("/plantas")
    @autenticado
    def listar():
        return jsonify({"plantas": [planta_detalle_a_json(d) for d in consultar.listar(g.identidad)]})

    @bp.post("/plantas")
    @autenticado
    def crear():
        datos = cuerpo_json()
        planta = gestionar.crear(g.identidad, texto(datos, "apodo"), texto(datos, "especie"))
        return jsonify(planta_a_json(planta)), 201

    @bp.get("/plantas/<int:planta_id>")
    @autenticado
    def detalle(planta_id: int):
        return jsonify(planta_detalle_a_json(consultar.detalle(g.identidad, planta_id)))

    @bp.patch("/plantas/<int:planta_id>")
    @autenticado
    def editar(planta_id: int):
        datos = cuerpo_json()
        planta = gestionar.editar(
            g.identidad,
            planta_id,
            texto(datos, "apodo", requerido=False),
            texto(datos, "especie", requerido=False),
        )
        return jsonify(planta_a_json(planta))

    @bp.delete("/plantas/<int:planta_id>")
    @autenticado
    def eliminar(planta_id: int):
        gestionar.eliminar(g.identidad, planta_id)
        return "", 204

    @bp.delete("/plantas/<int:planta_id>/vinculo")
    @autenticado
    def desvincularse(planta_id: int):
        gestionar.desvincularse(g.identidad, planta_id)
        return "", 204

    @bp.get("/plantas/<int:planta_id>/lecturas")
    @autenticado
    def historial(planta_id: int):
        mediciones = consultar.historial(
            g.identidad,
            planta_id,
            leer_fecha(request.args.get("desde"), "desde"),
            leer_fecha(request.args.get("hasta"), "hasta"),
            entero(request.args.get("limite"), "limite", 100),
        )
        return jsonify({"lecturas": [medicion_a_json(m) for m in mediciones]})

    return bp
