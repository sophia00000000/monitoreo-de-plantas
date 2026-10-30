"""Conexion SQLite compartida por los repositorios. Una conexion por operacion (seguro con hilos)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from matera.dominio.modelo import Especie, Parametro

ESQUEMA = Path(__file__).with_name("esquema.sql")


def a_texto(fecha: datetime | None) -> str | None:
    """Siempre UTC y con microsegundos, para que comparar textos equivalga a comparar fechas."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc).isoformat(timespec="microseconds")


def a_fecha(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class BaseDatosSqlite:
    def __init__(self, ruta: str | Path):
        self._ruta = Path(ruta)
        self._ruta.parent.mkdir(parents=True, exist_ok=True)

    def conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self._ruta, timeout=10, isolation_level=None)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion

    @contextmanager
    def lectura(self):
        conexion = self.conectar()
        try:
            yield conexion
        finally:
            conexion.close()

    @contextmanager
    def transaccion(self):
        """BEGIN IMMEDIATE: toma el bloqueo de escritura al inicio (RA21)."""
        conexion = self.conectar()
        try:
            conexion.execute("BEGIN IMMEDIATE")
            yield conexion
            conexion.execute("COMMIT")
        except BaseException:
            conexion.execute("ROLLBACK")
            raise
        finally:
            conexion.close()

    def inicializar(self, parametros: dict[str, Parametro], especies_semilla: list[Especie]) -> None:
        """Crea el esquema, registra los parametros y, si el catalogo esta vacio, lo siembra."""
        with self.lectura() as conexion:
            conexion.execute("PRAGMA journal_mode = WAL")
            conexion.executescript(ESQUEMA.read_text(encoding="utf-8"))
        with self.transaccion() as conexion:
            for p in parametros.values():
                conexion.execute(
                    """INSERT INTO parametro (codigo, unidad, min_fisico, max_fisico) VALUES (?, ?, ?, ?)
                       ON CONFLICT (codigo) DO UPDATE SET unidad = excluded.unidad,
                           min_fisico = excluded.min_fisico, max_fisico = excluded.max_fisico""",
                    (p.codigo, p.unidad, p.min_fisico, p.max_fisico),
                )
            vacio = conexion.execute("SELECT COUNT(*) FROM especie").fetchone()[0] == 0
            if vacio:
                for especie in especies_semilla:
                    guardar_especie(conexion, especie)


def ids_parametros(conexion: sqlite3.Connection) -> dict[str, int]:
    return {fila["codigo"]: fila["id"] for fila in conexion.execute("SELECT id, codigo FROM parametro")}


def guardar_especie(conexion: sqlite3.Connection, especie: Especie) -> int:
    conexion.execute(
        """INSERT INTO especie (nombre, nombre_cientifico, fuente, activa) VALUES (?, ?, ?, ?)
           ON CONFLICT (nombre) DO UPDATE SET nombre_cientifico = excluded.nombre_cientifico,
               fuente = excluded.fuente, activa = excluded.activa""",
        (especie.nombre, especie.nombre_cientifico, especie.fuente or "", int(especie.activa)),
    )
    especie_id = conexion.execute("SELECT id FROM especie WHERE nombre = ?", (especie.nombre,)).fetchone()[0]
    parametros = ids_parametros(conexion)
    conexion.execute("DELETE FROM rango_referencia WHERE especie_id = ?", (especie_id,))
    for codigo, rango in especie.rangos.items():
        conexion.execute(
            "INSERT INTO rango_referencia (especie_id, parametro_id, minimo, maximo) VALUES (?, ?, ?, ?)",
            (especie_id, parametros[codigo], rango.minimo, rango.maximo),
        )
    return especie_id
