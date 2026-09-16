import json
from pathlib import Path

from adaptadores.adapter import Adapter


class AdapterJson(Adapter):
    def __init__(self, ruta: str):
        self._ruta = Path(ruta)

    def cargar_configuracion_criterios(self) -> list[dict]:
        with self._ruta.open(encoding="utf-8") as archivo:
            return json.load(archivo)["plantas"]