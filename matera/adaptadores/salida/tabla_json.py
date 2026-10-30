import json
from pathlib import Path

from matera.dominio.modelo import Especie, Rango, normalizar_especie
from matera.dominio.puertos.salida import ConsultarRangosPort


class AdapterJson(ConsultarRangosPort):
    """Tabla de referencia en JSON (solo lectura)."""

    def __init__(self, ruta: str | Path):
        self._ruta = Path(ruta)

    def listar(self) -> list[Especie]:
        with self._ruta.open(encoding="utf-8") as archivo:
            datos = json.load(archivo)["especies"]
        return [
            Especie(
                nombre=normalizar_especie(item["nombre"]),
                nombre_cientifico=item.get("nombre_cientifico", ""),
                fuente=item.get("fuente", ""),
                rangos={
                    parametro: Rango(float(r["minimo"]), float(r["maximo"]))
                    for parametro, r in item["rangos"].items()
                },
                activa=item.get("activa", True),
            )
            for item in datos
        ]

    def obtener(self, nombre: str) -> Especie | None:
        nombre = normalizar_especie(nombre)
        return next((especie for especie in self.listar() if especie.nombre == nombre), None)
