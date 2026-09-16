import csv
from pathlib import Path

from adaptadores.adapter import Adapter


class AdapterCsv(Adapter):
    def __init__(self, ruta: str):
        self._ruta = Path(ruta)

    def cargar_configuracion_criterios(self) -> list[dict]:
        with self._ruta.open(encoding="utf-8") as archivo:
            plantas = {}
            for fila in csv.DictReader(archivo):
                planta = plantas.setdefault(
                    fila["tipo"],
                    {
                        "nombre": fila["nombre"],
                        "tipo": fila["tipo"],
                        "criterios": [],
                    },
                )
                planta["criterios"].append({
                    "nombre": fila["criterio"],
                    "minimo": float(fila["minimo"]),
                    "maximo": float(fila["maximo"]),
                    "unidad": fila["unidad"],
                })
            return list(plantas.values())