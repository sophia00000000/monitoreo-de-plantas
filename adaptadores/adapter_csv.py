import csv
from pathlib import Path

from dominio.puertos import FuenteConfiguracionPlantas
from dominio.normalizacion import normalizar_especie


class AdapterCsv(FuenteConfiguracionPlantas):
    def __init__(self, ruta: str):
        self._ruta = Path(ruta)

    def cargar_configuracion_criterios(self) -> list[dict]:
        with self._ruta.open(encoding="utf-8") as archivo:
            plantas = {}
            for fila in csv.DictReader(archivo):
                especie = normalizar_especie(fila["especie"])
                planta = plantas.setdefault(
                    especie,
                    {
                        "nombre": fila["nombre"],
                        "especie": especie,
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