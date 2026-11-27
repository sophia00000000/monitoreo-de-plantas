"""Reglas del animo de la mascota en SQLite (tabla regla_animo)."""
from matera.adaptadores.salida.base_datos import BaseDatosSqlite
from matera.dominio.modelo import Animo, EstadoParametro, ReglaAnimo
from matera.dominio.puertos.salida import ReglasAnimoPort


class ReglasAnimoBD(ReglasAnimoPort):
    """Solo traduce filas a ReglaAnimo. Sin cache: un cambio en la tabla aplica desde la siguiente lectura."""

    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def listar(self) -> list[ReglaAnimo]:
        with self._bd.lectura() as conexion:
            filas = conexion.execute(
                """SELECT p.codigo, r.estado, r.animo, r.prioridad
                   FROM regla_animo r JOIN parametro p ON p.id = r.parametro_id
                   ORDER BY r.prioridad, r.id"""
            ).fetchall()
        return [
            ReglaAnimo(
                parametro=f["codigo"],
                estado=EstadoParametro(f["estado"]),
                animo=Animo(f["animo"]),
                prioridad=f["prioridad"],
            )
            for f in filas
        ]
