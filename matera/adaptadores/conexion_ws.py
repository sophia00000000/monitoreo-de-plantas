import json
import threading


class ConexionWs:
    """Envoltorio de un socket WebSocket: serializa a JSON y evita envios simultaneos desde varios hilos."""

    def __init__(self, ws):
        self._ws = ws
        self._candado = threading.Lock()

    def enviar(self, mensaje: dict) -> bool:
        try:
            with self._candado:
                self._ws.send(json.dumps(mensaje))
            return True
        except Exception:
            return False

    def recibir(self, timeout: float | None = None):
        return self._ws.receive(timeout=timeout)

    def cerrar(self, motivo: str = "") -> None:
        try:
            self._ws.close(reason=1008, message=motivo)
        except Exception:
            pass
