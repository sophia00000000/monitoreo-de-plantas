"""Tabla de referencia en SQLite: implementa la lectura (ConsultarRangosPort) y la gestion
(RepositorioEspeciesPort) con dos interfaces separadas (ISP)."""
from matera.adaptadores.salida.base_datos import (
    BaseDatosSqlite,
    a_fecha,
    a_texto,
    guardar_especie,
)
from matera.dominio.modelo import (
    Especie,
    EstadoSolicitud,
    Rango,
    SolicitudEspecie,
    normalizar_especie,
)
from matera.dominio.puertos.salida import ConsultarRangosPort, RepositorioEspeciesPort


class SqliteEspecies(ConsultarRangosPort, RepositorioEspeciesPort):
    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    # ------------------------------------------------ ConsultarRangosPort

    def listar(self) -> list[Especie]:
        with self._bd.lectura() as conexion:
            filas = conexion.execute("SELECT * FROM especie WHERE activa = 1 ORDER BY nombre").fetchall()
            return [self._especie(conexion, fila) for fila in filas]

    def obtener(self, nombre: str) -> Especie | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute(
                "SELECT * FROM especie WHERE nombre = ?", (normalizar_especie(nombre),)
            ).fetchone()
            return self._especie(conexion, fila) if fila else None

    # ------------------------------------------------ RepositorioEspeciesPort

    def existe(self, nombre: str) -> bool:
        with self._bd.lectura() as conexion:
            return conexion.execute(
                "SELECT 1 FROM especie WHERE nombre = ? AND activa = 1", (nombre,)
            ).fetchone() is not None

    def guardar_especie(self, especie: Especie) -> Especie:
        with self._bd.transaccion() as conexion:
            especie_id = guardar_especie(conexion, especie)
        return Especie(
            nombre=especie.nombre,
            nombre_cientifico=especie.nombre_cientifico,
            fuente=especie.fuente,
            rangos=dict(especie.rangos),
            activa=especie.activa,
            id=especie_id,
        )

    def desactivar_especie(self, nombre: str) -> bool:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute("UPDATE especie SET activa = 0 WHERE nombre = ?", (nombre,))
            return cursor.rowcount == 1

    def crear_solicitud(self, solicitud: SolicitudEspecie) -> SolicitudEspecie:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """INSERT INTO solicitud_especie (usuario_id, nombre_propuesto, justificacion, estado, creada_en)
                   VALUES (?, ?, ?, ?, ?)""",
                (solicitud.usuario_id, solicitud.nombre_propuesto, solicitud.justificacion,
                 solicitud.estado.value, a_texto(solicitud.creada_en)),
            )
            solicitud.id = cursor.lastrowid
        return solicitud

    def obtener_solicitud(self, solicitud_id: int) -> SolicitudEspecie | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute("SELECT * FROM solicitud_especie WHERE id = ?", (solicitud_id,)).fetchone()
            return self._solicitud(fila) if fila else None

    def listar_solicitudes(self, usuario_id: int | None, estado: str | None) -> list[SolicitudEspecie]:
        consulta = "SELECT * FROM solicitud_especie WHERE 1 = 1"
        argumentos: list = []
        if usuario_id is not None:
            consulta += " AND usuario_id = ?"
            argumentos.append(usuario_id)
        if estado is not None:
            consulta += " AND estado = ?"
            argumentos.append(estado)
        with self._bd.lectura() as conexion:
            filas = conexion.execute(consulta + " ORDER BY creada_en DESC", argumentos).fetchall()
            return [self._solicitud(fila) for fila in filas]

    def resolver_solicitud(self, solicitud: SolicitudEspecie) -> bool:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """UPDATE solicitud_especie SET estado = ?, resuelta_por = ?, resuelta_en = ?, especie_id = ?
                   WHERE id = ? AND estado = 'PENDIENTE'""",
                (solicitud.estado.value, solicitud.resuelta_por, a_texto(solicitud.resuelta_en),
                 solicitud.especie_id, solicitud.id),
            )
            return cursor.rowcount == 1

    # ------------------------------------------------ mapeo

    @staticmethod
    def _especie(conexion, fila) -> Especie:
        rangos = conexion.execute(
            """SELECT p.codigo, r.minimo, r.maximo FROM rango_referencia r
               JOIN parametro p ON p.id = r.parametro_id WHERE r.especie_id = ? ORDER BY p.id""",
            (fila["id"],),
        ).fetchall()
        return Especie(
            id=fila["id"],
            nombre=fila["nombre"],
            nombre_cientifico=fila["nombre_cientifico"] or "",
            fuente=fila["fuente"],
            activa=bool(fila["activa"]),
            rangos={r["codigo"]: Rango(r["minimo"], r["maximo"]) for r in rangos},
        )

    @staticmethod
    def _solicitud(fila) -> SolicitudEspecie:
        return SolicitudEspecie(
            id=fila["id"],
            usuario_id=fila["usuario_id"],
            nombre_propuesto=fila["nombre_propuesto"],
            justificacion=fila["justificacion"] or "",
            estado=EstadoSolicitud(fila["estado"]),
            creada_en=a_fecha(fila["creada_en"]),
            resuelta_por=fila["resuelta_por"],
            resuelta_en=a_fecha(fila["resuelta_en"]),
            especie_id=fila["especie_id"],
        )
