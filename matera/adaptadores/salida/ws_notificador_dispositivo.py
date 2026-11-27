import threading

from matera.adaptadores.conexion_ws import ConexionWs
from matera.dominio.modelo import Animo
from matera.dominio.puertos.salida import NotificadorDispositivoPort


class _Emparejamiento:
    def __init__(self, conexion: ConexionWs):
        self.conexion = conexion
        self.confirmado = threading.Event()


class WsNotificadorDispositivo(NotificadorDispositivoPort):
    """Conexiones abiertas de dispositivos en emparejamiento, una por MAC (RA22).

    Entrega el token por la conexion y espera el acuse {"tipo": "token_recibido"}.
    Si no llega a tiempo devuelve False y el dominio revierte la vinculacion.
    """

    def __init__(self, espera_confirmacion: float = 10.0):
        self._operando: dict[str, ConexionWs] = {}
        self._espera = espera_confirmacion
        self._abiertas: dict[str, _Emparejamiento] = {}
        self._candado = threading.Lock()

    def registrar(self, mac: str, conexion: ConexionWs) -> bool:
        with self._candado:
            if mac in self._abiertas:
                return False
            self._abiertas[mac] = _Emparejamiento(conexion)
            return True

    def quitar(self, mac: str, conexion: ConexionWs) -> None:
        with self._candado:
            actual = self._abiertas.get(mac)
            if actual is not None and actual.conexion is conexion:
                del self._abiertas[mac]

    def confirmar(self, mac: str) -> None:
        with self._candado:
            actual = self._abiertas.get(mac)
        if actual is not None:
            actual.confirmado.set()

    def entregar_token(self, mac: str, token: str) -> bool:
        with self._candado:
            actual = self._abiertas.get(mac)
        if actual is None:
            return False
        actual.confirmado.clear()
        if not actual.conexion.enviar({"tipo": "token", "token": token}):
            return False
        entregado = actual.confirmado.wait(self._espera)
        if entregado:
            self.quitar(mac, actual.conexion)  # la ventana se cierra al vincular
        return entregado

    def registrar_operando(self, mac: str, conexion: ConexionWs) -> None:
        with self._candado:
            self._operando[mac] = conexion

    def quitar_operando(self, mac: str, conexion: ConexionWs) -> None:
        with self._candado:
            if self._operando.get(mac) is conexion:
                del self._operando[mac]

    def avisar_desvinculacion(self, mac: str) -> bool:
        return self._enviar(mac, {"tipo": "desvinculado"})

    def notificar_animo(self, mac: str, animo: Animo) -> bool:
        """{"tipo": "mascota", "animo": ...}: lo interpreta ConexionWS::alMensaje del firmware."""
        return self._enviar(mac, {"tipo": "mascota", "animo": animo.value})

    def _enviar(self, mac: str, mensaje: dict) -> bool:
        """A la conexion autenticada ("operando") de esa MAC. False si no hay conexion o el envio fallo."""
        with self._candado:
            conexion = self._operando.get(mac)
        return conexion.enviar(mensaje) if conexion else False
