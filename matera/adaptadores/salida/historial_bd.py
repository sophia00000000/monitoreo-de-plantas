"""Historial de lecturas en SQLite: medicion, medicion_valor, diagnostico y diagnostico_detalle."""
from datetime import datetime

from matera.adaptadores.salida.base_datos import BaseDatosSqlite, a_fecha, a_texto, ids_parametros
from matera.dominio.modelo import (
    Diagnostico,
    EstadoGlobal,
    EstadoParametro,
    EvaluacionParametro,
    Lectura,
    Medicion,
    OrigenLectura,
)
from matera.dominio.puertos.salida import HistorialLecturasPort


class RepoLecturas(HistorialLecturasPort):
    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def guardar(self, medicion: Medicion) -> Medicion:
        with self._bd.transaccion() as conexion:
            parametros = ids_parametros(conexion)
            medicion_id = conexion.execute(
                "INSERT INTO medicion (planta_id, dispositivo_id, tomada_en, origen) VALUES (?, ?, ?, ?)",
                (medicion.planta_id, medicion.dispositivo_id, a_texto(medicion.tomada_en), medicion.origen.value),
            ).lastrowid
            for codigo, valor in medicion.lectura.valores.items():
                if codigo in parametros:
                    conexion.execute(
                        "INSERT INTO medicion_valor (medicion_id, parametro_id, valor) VALUES (?, ?, ?)",
                        (medicion_id, parametros[codigo], float(valor)),
                    )
            diagnostico_id = conexion.execute(
                "INSERT INTO diagnostico (medicion_id, estado_global, evaluado_en) VALUES (?, ?, ?)",
                (medicion_id, medicion.diagnostico.estado_global.value, a_texto(medicion.evaluado_en)),
            ).lastrowid
            for p in medicion.diagnostico.parametros:
                conexion.execute(
                    """INSERT INTO diagnostico_detalle
                       (diagnostico_id, parametro_id, estado, recomendacion, minimo, maximo)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (diagnostico_id, parametros[p.parametro], p.estado.value, p.recomendacion, p.minimo, p.maximo),
                )
        medicion.id = medicion_id
        return medicion

    def ultima(self, planta_id: int) -> Medicion | None:
        resultado = self.listar(planta_id, None, None, 1)
        return resultado[0] if resultado else None

    def listar(
        self, planta_id: int, desde: datetime | None, hasta: datetime | None, limite: int
    ) -> list[Medicion]:
        consulta = """SELECT m.*, d.id AS diagnostico_id, d.estado_global, d.evaluado_en, p.especie
                      FROM medicion m
                      JOIN diagnostico d ON d.medicion_id = m.id
                      JOIN (SELECT pl.id, e.nombre AS especie FROM planta pl JOIN especie e ON e.id = pl.especie_id) p
                        ON p.id = m.planta_id
                      WHERE m.planta_id = ?"""
        argumentos: list = [planta_id]
        if desde is not None:
            consulta += " AND m.tomada_en >= ?"
            argumentos.append(a_texto(desde))
        if hasta is not None:
            consulta += " AND m.tomada_en <= ?"
            argumentos.append(a_texto(hasta))
        consulta += " ORDER BY m.tomada_en DESC, m.id DESC LIMIT ?"
        argumentos.append(limite)
        with self._bd.lectura() as conexion:
            return [self._medicion(conexion, fila) for fila in conexion.execute(consulta, argumentos).fetchall()]

    @staticmethod
    def _medicion(conexion, fila) -> Medicion:
        valores = {
            v["codigo"]: v["valor"]
            for v in conexion.execute(
                """SELECT p.codigo, v.valor FROM medicion_valor v JOIN parametro p ON p.id = v.parametro_id
                   WHERE v.medicion_id = ? ORDER BY p.id""",
                (fila["id"],),
            )
        }
        detalles = conexion.execute(
            """SELECT p.codigo, p.unidad, d.estado, d.recomendacion, d.minimo, d.maximo
               FROM diagnostico_detalle d JOIN parametro p ON p.id = d.parametro_id
               WHERE d.diagnostico_id = ? ORDER BY p.id""",
            (fila["diagnostico_id"],),
        ).fetchall()
        diagnostico = Diagnostico(
            especie=fila["especie"],
            estado_global=EstadoGlobal(fila["estado_global"]),
            parametros=tuple(
                EvaluacionParametro(
                    parametro=d["codigo"],
                    valor=valores.get(d["codigo"]),
                    unidad=d["unidad"],
                    minimo=d["minimo"],
                    maximo=d["maximo"],
                    estado=EstadoParametro(d["estado"]),
                    recomendacion=d["recomendacion"],
                )
                for d in detalles
            ),
        )
        return Medicion(
            id=fila["id"],
            planta_id=fila["planta_id"],
            dispositivo_id=fila["dispositivo_id"],
            tomada_en=a_fecha(fila["tomada_en"]),
            origen=OrigenLectura(fila["origen"]),
            lectura=Lectura(valores),
            diagnostico=diagnostico,
            evaluado_en=a_fecha(fila["evaluado_en"]),
        )
