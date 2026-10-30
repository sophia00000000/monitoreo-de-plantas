import threading
from collections import defaultdict

from matera.adaptadores.conexion_ws import ConexionWs
from matera.adaptadores.serializacion import medicion_a_json
from matera.dominio.modelo import Medicion
from matera.dominio.puertos.salida import NotificadorEstadoPort


class WsNotificador(NotificadorEstadoPort):
    """Empuja el estado nuevo de una planta a los navegadores suscritos (RF19)."""

    def __init__(self):
        self._suscriptores: dict[int, set[ConexionWs]] = defaultdict(set)
        self._candado = threading.Lock()

    def suscribir(self, planta_id: int, conexion: ConexionWs) -> None:
        with self._candado:
            self._suscriptores[planta_id].add(conexion)

    def quitar(self, conexion: ConexionWs) -> None:
        with self._candado:
            for conexiones in self._suscriptores.values():
                conexiones.discard(conexion)

    def publicar(self, medicion: Medicion) -> None:
        with self._candado:
            destinatarios = list(self._suscriptores.get(medicion.planta_id, ()))
        mensaje = {"tipo": "estado", "planta_id": medicion.planta_id, "medicion": medicion_a_json(medicion)}
        for conexion in destinatarios:
            if not conexion.enviar(mensaje):
                self.quitar(conexion)
