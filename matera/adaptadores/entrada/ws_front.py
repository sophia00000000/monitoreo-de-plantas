"""Canal WebSocket del front (RF19). El JWT llega en el primer mensaje, no en la URL,
para que no quede en los logs del servidor (RA25)."""
import json

from matera.adaptadores.conexion_ws import ConexionWs
from matera.adaptadores.entrada.http.comun import NoAutenticado
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.salida.ws_notificador import WsNotificador
from matera.dominio.errores import ErrorDominio
from matera.dominio.puertos.entrada import ConsultarPlantaPort

ESPERA_AUTENTICACION = 10


class WsFrontAdapter:
    def __init__(self, verificador: JwtVerificador, consultar: ConsultarPlantaPort, notificador: WsNotificador):
        self._verificador = verificador
        self._consultar = consultar
        self._notificador = notificador

    def registrar_en(self, sock) -> None:
        sock.route("/ws/front", endpoint="ws_front")(self.atender)

    def atender(self, ws) -> None:
        conexion = ConexionWs(ws)
        try:
            identidad = self._autenticar(conexion)
            if identidad is None:
                return
            conexion.enviar({"tipo": "autenticado"})
            while True:
                crudo = conexion.recibir()
                if crudo is None:
                    continue
                mensaje = _json(crudo)
                if mensaje.get("tipo") != "suscribir":
                    conexion.enviar({"tipo": "error", "error": "MENSAJE_INVALIDO", "mensaje": "Tipo desconocido."})
                    continue
                try:
                    planta_id = int(mensaje.get("planta_id"))
                    self._consultar.detalle(identidad, planta_id)  # la regla de propiedad la aplica el dominio
                except (TypeError, ValueError):
                    conexion.enviar({"tipo": "error", "error": "DATOS_INVALIDOS", "mensaje": "planta_id invalido."})
                    continue
                except ErrorDominio as error:
                    conexion.enviar({"tipo": "error", "error": error.codigo, "mensaje": error.mensaje})
                    continue
                self._notificador.suscribir(planta_id, conexion)
                conexion.enviar({"tipo": "suscrito", "planta_id": planta_id})
        except Exception:
            pass  # conexion cerrada por el navegador
        finally:
            self._notificador.quitar(conexion)

    def _autenticar(self, conexion: ConexionWs):
        crudo = conexion.recibir(timeout=ESPERA_AUTENTICACION)
        mensaje = _json(crudo) if crudo else {}
        try:
            if mensaje.get("tipo") != "autenticar":
                raise NoAutenticado()
            return self._verificador.verificar(mensaje.get("token"))
        except NoAutenticado:
            conexion.enviar({"tipo": "error", "error": "NO_AUTENTICADO", "mensaje": "Sesion invalida."})
            conexion.cerrar("no autenticado")
            return None


def _json(crudo) -> dict:
    try:
        datos = json.loads(crudo)
        return datos if isinstance(datos, dict) else {}
    except (TypeError, ValueError):
        return {}
