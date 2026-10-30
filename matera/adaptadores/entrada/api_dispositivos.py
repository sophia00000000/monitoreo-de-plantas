"""Adaptadores de entrada de los dispositivos (ESP32 o simulador).

- LecturasController: POST /api/v1/dispositivos/<mac>/lecturas con "Authorization: Bearer <token>".
- WsDispositivoAdapter: canal WebSocket /ws/dispositivos para anunciarse, recibir el token y reportar.

Protocolo WS (mensajes JSON):
  -> {"tipo": "anuncio", "mac": "AA:BB:CC:DD:EE:FF"}          <- {"tipo": "emparejando", "expira_en": ...}
  <- {"tipo": "token", "token": "..."}                        -> {"tipo": "token_recibido"}
  -> {"tipo": "autenticar", "mac": "...", "token": "..."}     <- {"tipo": "autenticado"}
  -> {"tipo": "lectura", "humedad": 45, "luz": 300, "temperatura": 22, "tomada_en": "ISO-8601"}
                                                              <- {"tipo": "diagnostico", ...}
  Errores: <- {"tipo": "error", "error": CODIGO, "mensaje": "..."}
"""
import json

from flask import Blueprint, jsonify, request

from matera.adaptadores.conexion_ws import ConexionWs
from matera.adaptadores.entrada.http.comun import (
    NoAutenticado,
    cuerpo_json,
    leer_fecha,
    leer_lectura,
    token_bearer,
)
from matera.adaptadores.entrada.http.limitador import LimitadorIntentos
from matera.adaptadores.salida.ws_notificador_dispositivo import WsNotificadorDispositivo
from matera.adaptadores.serializacion import diagnostico_a_json, medicion_a_json
from matera.dominio.errores import CredencialesInvalidas, DatosInvalidos, ErrorDominio
from matera.dominio.modelo import OrigenLectura, normalizar_mac
from matera.dominio.puertos.entrada import (
    AutenticarDispositivoPort,
    EmparejarDispositivoPort,
    RegistrarLecturaPort,
)


def crear_lecturas_controller(
    autenticar: AutenticarDispositivoPort,
    registrar: RegistrarLecturaPort,
) -> Blueprint:
    bp = Blueprint("lecturas_dispositivo", __name__, url_prefix="/api/v1/dispositivos")

    @bp.post("/<mac>/lecturas")
    def reportar(mac: str):
        token = token_bearer()
        if token is None:
            raise NoAutenticado("Falta el token del dispositivo.")
        dispositivo_id = autenticar.autenticar(mac, token)
        datos = cuerpo_json()
        medicion = registrar.registrar(
            dispositivo_id,
            leer_lectura(datos),
            leer_fecha(datos.get("tomada_en"), "tomada_en"),
            OrigenLectura.HTTP,
        )
        return jsonify(medicion_a_json(medicion)), 201

    return bp


class WsDispositivoAdapter:
    def __init__(
        self,
        emparejar: EmparejarDispositivoPort,
        autenticar: AutenticarDispositivoPort,
        registrar: RegistrarLecturaPort,
        conexiones: WsNotificadorDispositivo,
        limitador: LimitadorIntentos,
    ):
        self._emparejar = emparejar
        self._autenticar = autenticar
        self._registrar = registrar
        self._conexiones = conexiones
        self._limitador = limitador

    def registrar_en(self, sock) -> None:
        sock.route("/ws/dispositivos", endpoint="ws_dispositivos")(self.atender)

    def atender(self, ws) -> None:
        conexion = ConexionWs(ws)
        sesion = {"mac_emparejando": None, "dispositivo_id": None}
        try:
            while True:
                crudo = conexion.recibir()
                if crudo is None:
                    continue
                try:
                    respuesta = self._procesar(conexion, sesion, crudo)
                except CredencialesInvalidas as error:
                    conexion.enviar(_error(error.codigo, error.mensaje))
                    if sesion["dispositivo_id"] is None:
                        conexion.cerrar("credenciales invalidas")
                        return
                    continue
                except ErrorDominio as error:
                    respuesta = _error(error.codigo, error.mensaje, error.detalle)
                if respuesta is not None:
                    conexion.enviar(respuesta)
        except Exception:
            pass  # el dispositivo cerro la conexion
        finally:
            mac = sesion["mac_emparejando"]
            if mac is not None:
                self._conexiones.quitar(mac, conexion)
                self._emparejar.cancelar(mac)

    def _procesar(self, conexion: ConexionWs, sesion: dict, crudo) -> dict | None:
        mensaje = _json(crudo)
        tipo = mensaje.get("tipo")

        if tipo == "anuncio":
            mac = normalizar_mac(mensaje.get("mac"))
            if not self._conexiones.registrar(mac, conexion):
                raise DatosInvalidos("Ya hay una conexion de emparejamiento abierta para esta MAC.")
            try:
                expira_en = self._emparejar.anunciar(mac)
            except ErrorDominio:
                self._conexiones.quitar(mac, conexion)
                raise
            sesion["mac_emparejando"] = mac
            return {"tipo": "emparejando", "mac": mac, "expira_en": expira_en.isoformat()}

        if tipo == "token_recibido":
            if sesion["mac_emparejando"]:
                self._conexiones.confirmar(sesion["mac_emparejando"])
            return None

        if tipo == "autenticar":
            if not self._limitador.permitir(f"ws-dispositivo:{request.remote_addr}"):
                raise CredencialesInvalidas("Demasiados intentos.")
            sesion["dispositivo_id"] = self._autenticar.autenticar(mensaje.get("mac"), mensaje.get("token"))
            sesion["mac_emparejando"] = None
            return {"tipo": "autenticado"}

        if tipo == "lectura":
            if sesion["dispositivo_id"] is None:
                raise CredencialesInvalidas("Primero debe autenticarse.")
            medicion = self._registrar.registrar(
                sesion["dispositivo_id"],
                leer_lectura(mensaje),
                leer_fecha(mensaje.get("tomada_en"), "tomada_en"),
                OrigenLectura.WS,
            )
            return {
                "tipo": "diagnostico",
                "medicion_id": medicion.id,
                **diagnostico_a_json(medicion.diagnostico),
            }

        raise DatosInvalidos("Mensaje no reconocido.")


def _json(crudo) -> dict:
    try:
        datos = json.loads(crudo)
    except (TypeError, ValueError):
        raise DatosInvalidos("El mensaje no es JSON valido.") from None
    if not isinstance(datos, dict):
        raise DatosInvalidos("El mensaje debe ser un objeto JSON.")
    return datos


def _error(codigo: str, mensaje: str, detalle: dict | None = None) -> dict:
    return {"tipo": "error", "error": codigo, "mensaje": mensaje, "detalle": detalle or {}}
