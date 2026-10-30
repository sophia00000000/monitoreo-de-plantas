"""Punto unico de composicion (RA14): aqui, y solo aqui, se decide que adaptador va en cada puerto."""
from datetime import timedelta

from flask import Flask
from flask_cors import CORS
from flask_sock import Sock

from matera.adaptadores.entrada.api_dispositivos import WsDispositivoAdapter, crear_lecturas_controller
from matera.adaptadores.entrada.http.admin_controller import crear_admin_controller
from matera.adaptadores.entrada.http.auth_controller import crear_auth_controller
from matera.adaptadores.entrada.http.catalogo_controller import crear_catalogo_controller
from matera.adaptadores.entrada.http.comun import registrar_manejadores_error
from matera.adaptadores.entrada.http.compartir_controller import crear_compartir_controller
from matera.adaptadores.entrada.http.especies_controller import crear_especies_controller
from matera.adaptadores.entrada.http.jwt_verificador import JwtVerificador
from matera.adaptadores.entrada.http.limitador import LimitadorIntentos
from matera.adaptadores.entrada.http.planta_controller import crear_planta_controller
from matera.adaptadores.entrada.http.vinculacion_controller import crear_vinculacion_controller
from matera.adaptadores.entrada.ws_front import WsFrontAdapter
from matera.adaptadores.salida.auditoria_bd import SqliteAuditoria
from matera.adaptadores.salida.base_datos import BaseDatosSqlite
from matera.adaptadores.salida.historial_bd import RepoLecturas
from matera.adaptadores.salida.reloj import RelojSistema
from matera.adaptadores.salida.seguridad import BcryptHasher, JwtAdapter, TokenOpacoGenerator
from matera.adaptadores.salida.sqlite_repository import (
    SqliteDispositivos,
    SqliteInvitaciones,
    SqlitePlantas,
    SqliteUsuarios,
)
from matera.adaptadores.salida.tabla_bd import SqliteEspecies
from matera.adaptadores.salida.tabla_csv import AdapterCsv
from matera.adaptadores.salida.tabla_json import AdapterJson
from matera.adaptadores.salida.ws_notificador import WsNotificador
from matera.adaptadores.salida.ws_notificador_dispositivo import WsNotificadorDispositivo
from matera.config import Configuracion
from matera.dominio.modelo import PARAMETROS
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.puertos.salida import ConsultarRangosPort
from matera.dominio.servicios.autenticacion import AutenticacionService
from matera.dominio.servicios.catalogo import CatalogoService
from matera.dominio.servicios.compartir import CompartirPlantaService
from matera.dominio.servicios.consulta_planta import ConsultaPlantaService
from matera.dominio.servicios.cuentas import CuentasService
from matera.dominio.servicios.dispositivos import AutenticacionDispositivoService, VincularDispositivoService
from matera.dominio.servicios.especies import EspeciesService
from matera.dominio.servicios.plantas import PlantasService
from matera.dominio.servicios.registrar_lectura import RegistrarLecturaService
from matera.dominio.validador import Evaluador


def _tabla_referencia(config: Configuracion, especies_bd: SqliteEspecies) -> ConsultarRangosPort:
    """RA15: la tabla de referencia se elige por configuracion, sin tocar codigo."""
    fuentes = {
        "csv": lambda: AdapterCsv(config.ruta_csv),
        "json": lambda: AdapterJson(config.ruta_json),
        "sqlite": lambda: especies_bd,
    }
    if config.fuente_especies not in fuentes:
        raise ValueError(f"MATERA_FUENTE_ESPECIES debe ser una de: {', '.join(fuentes)}")
    return fuentes[config.fuente_especies]()


def create_app(config: Configuracion | None = None) -> Flask:
    config = config or Configuracion.desde_entorno()

    # ---------------------------------------------------- adaptadores de salida
    reloj = RelojSistema()
    bd = BaseDatosSqlite(config.ruta_bd)
    bd.inicializar(PARAMETROS, especies_semilla=AdapterCsv(config.ruta_csv).listar())
    especies_bd = SqliteEspecies(bd)
    rangos = _tabla_referencia(config, especies_bd)
    usuarios = SqliteUsuarios(bd)
    plantas = SqlitePlantas(bd)
    dispositivos = SqliteDispositivos(bd)
    invitaciones = SqliteInvitaciones(bd)
    historial = RepoLecturas(bd)
    auditoria = SqliteAuditoria(bd)
    hasher = BcryptHasher(config.rondas_bcrypt)
    emisor_jwt = JwtAdapter(config.jwt_secreto, reloj, timedelta(minutes=config.jwt_minutos))
    generador_tokens = TokenOpacoGenerator()
    notificador_estado = WsNotificador()
    notificador_dispositivo = WsNotificadorDispositivo(config.espera_token_dispositivo)

    # ---------------------------------------------------- dominio (casos de uso)
    politica = PoliticaPropiedad(plantas, auditoria, reloj)
    evaluador = Evaluador(rangos)
    catalogo = CatalogoService(rangos)
    autenticacion = AutenticacionService(usuarios, hasher, emisor_jwt, reloj, auditoria)
    plantas_service = PlantasService(plantas, rangos, dispositivos, politica, reloj, auditoria)
    consulta = ConsultaPlantaService(plantas, dispositivos, historial, politica)
    vinculacion = VincularDispositivoService(
        dispositivos, politica, generador_tokens, notificador_dispositivo, reloj, auditoria
    )
    autenticacion_dispositivo = AutenticacionDispositivoService(dispositivos, generador_tokens, reloj, auditoria)
    registrar_lectura = RegistrarLecturaService(
        dispositivos, plantas, evaluador, historial, notificador_estado, reloj
    )
    compartir = CompartirPlantaService(
        plantas, invitaciones, politica, generador_tokens, reloj, auditoria,
        duracion=timedelta(minutes=config.invitacion_minutos),
    )
    cuentas = CuentasService(usuarios)
    especies = EspeciesService(especies_bd, reloj)

    if config.admin_usuario and config.admin_email and config.admin_password:
        autenticacion.asegurar_admin(config.admin_usuario, config.admin_email, config.admin_password)

    # ---------------------------------------------------- adaptadores de entrada
    app = Flask(__name__, static_folder=None)  # RA1: el backend solo responde JSON
    CORS(app, resources={r"/api/*": {"origins": config.origenes_cors}})
    sock = Sock(app)
    verificador = JwtVerificador(config.jwt_secreto)
    limitador = LimitadorIntentos(config.limite_intentos, config.ventana_limite_segundos)

    app.register_blueprint(crear_catalogo_controller(catalogo))
    app.register_blueprint(crear_auth_controller(autenticacion, limitador))
    app.register_blueprint(crear_planta_controller(evaluador, plantas_service, consulta, verificador))
    app.register_blueprint(crear_vinculacion_controller(vinculacion, verificador, limitador))
    app.register_blueprint(crear_compartir_controller(compartir, verificador, limitador))
    app.register_blueprint(crear_especies_controller(especies, verificador))
    app.register_blueprint(crear_admin_controller(cuentas, verificador))
    WsFrontAdapter(verificador, consulta, notificador_estado).registrar_en(sock)

    # Dispositivos (ESP32 / simulador): HTTP y WebSocket
    app.register_blueprint(crear_lecturas_controller(autenticacion_dispositivo, registrar_lectura))
    WsDispositivoAdapter(
        vinculacion, autenticacion_dispositivo, registrar_lectura, notificador_dispositivo, limitador
    ).registrar_en(sock)

    registrar_manejadores_error(app)
    app.extensions["matera"] = {
        "config": config,
        "notificador_dispositivo": notificador_dispositivo,
        "emparejar": vinculacion,
    }
    return app
