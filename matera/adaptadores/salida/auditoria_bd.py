from matera.adaptadores.salida.base_datos import BaseDatosSqlite, a_texto
from matera.dominio.modelo import EntradaAuditoria
from matera.dominio.puertos.salida import AuditoriaPort


class SqliteAuditoria(AuditoriaPort):
    """Registro de eventos sensibles (RA26). Las entradas nunca contienen tokens (RA25)."""

    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def registrar(self, entrada: EntradaAuditoria) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                """INSERT INTO auditoria (usuario_id, dispositivo_id, planta_id, evento, detalle, ocurrido_en)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entrada.usuario_id, entrada.dispositivo_id, entrada.planta_id,
                 entrada.evento.value, entrada.detalle, a_texto(entrada.ocurrido_en)),
            )
