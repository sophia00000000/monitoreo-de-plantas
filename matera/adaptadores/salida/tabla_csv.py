import csv
from pathlib import Path

from matera.dominio.modelo import Especie, Rango, normalizar_especie
from matera.dominio.puertos.salida import ConsultarRangosPort


class AdapterCsv(ConsultarRangosPort):
    """Tabla de referencia en CSV: una fila por especie y parametro (solo lectura)."""

    def __init__(self, ruta: str | Path):
        self._ruta = Path(ruta)

    def listar(self) -> list[Especie]:
        datos: dict[str, dict] = {}
        with self._ruta.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                nombre = normalizar_especie(fila["especie"])
                especie = datos.setdefault(nombre, {
                    "nombre_cientifico": fila.get("nombre_cientifico", ""),
                    "fuente": fila.get("fuente", ""),
                    "rangos": {},
                })
                especie["rangos"][fila["parametro"].strip()] = Rango(float(fila["minimo"]), float(fila["maximo"]))
        return [
            Especie(nombre=nombre, nombre_cientifico=d["nombre_cientifico"], fuente=d["fuente"], rangos=d["rangos"])
            for nombre, d in datos.items()
        ]

    def obtener(self, nombre: str) -> Especie | None:
        nombre = normalizar_especie(nombre)
        return next((especie for especie in self.listar() if especie.nombre == nombre), None)
