from flask import Flask, render_template
from pathlib import Path

from adaptadores.adapter_csv import AdapterCsv
from adaptadores.adapter_json import AdapterJson
from controladores.planta_controller import crear_blueprint
from repositorios.planta_repository import PlantaRepository
from servicios.criterios import CriterioFactory
from servicios.evaluador import Evaluador


def create_app():
    app = Flask(__name__)
    ruta_configuracion = Path(__file__).parent / "configuracion" / "plantas.csv"
    repository = PlantaRepository(AdapterCsv(str(ruta_configuracion)))
    evaluador = Evaluador(repository, CriterioFactory())
    app.register_blueprint(crear_blueprint(evaluador))

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
