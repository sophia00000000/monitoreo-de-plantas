from flask import Flask, jsonify
from flask_cors import CORS
from pathlib import Path

from adaptadores.adapter_csv import AdapterCsv
from controladores.planta_controller import crear_blueprint
from repositorios.planta_repository import PlantaRepository
from dominio.criterios import CriterioFactory
from servicios.evaluador import Evaluador


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "http://127.0.0.1:5500"}})
    ruta_configuracion = Path(__file__).parent / "configuracion" / "plantas.csv"
    repository = PlantaRepository(AdapterCsv(str(ruta_configuracion)))
    evaluador = Evaluador(repository, CriterioFactory())
    app.register_blueprint(crear_blueprint(evaluador))

    @app.errorhandler(404)
    def recurso_no_encontrado(error):
        return jsonify({
            "error": "RECURSO_NO_ENCONTRADO",
            "mensaje": "El recurso solicitado no existe.",
            "detalle": {},
        }), 404

    @app.errorhandler(405)
    def metodo_no_permitido(error):
        return jsonify({
            "error": "METODO_NO_PERMITIDO",
            "mensaje": "El metodo HTTP no esta permitido para este recurso.",
            "detalle": {},
        }), 405

    @app.errorhandler(500)
    def error_interno(error):
        return jsonify({
            "error": "ERROR_INTERNO",
            "mensaje": "Ocurrio un error interno en el servidor.",
            "detalle": {},
        }), 500

    return app
