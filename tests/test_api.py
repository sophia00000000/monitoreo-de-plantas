"""Pruebas de integracion de los adaptadores: Flask + SQLite en un archivo temporal.

No son pruebas del dominio (esas estan en test_dominio.py); verifican que la traduccion HTTP,
la persistencia y la composicion funcionen juntas.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from matera.adaptadores.salida.base_datos import BaseDatosSqlite
from matera.adaptadores.salida.historial_bd import RepoLecturas
from matera.adaptadores.salida.reglas_animo_bd import ReglasAnimoBD
from matera.app import create_app
from matera.config import Configuracion
from matera.dominio.modelo import PARAMETROS, Animo
from tests.dobles import REGLAS_ANIMO

OPTIMA = {"humedad": 40, "luz": 300, "temperatura": 22}
MAC = "AA:BB:CC:DD:EE:01"


class _DispositivoFalso:
    """Conexion WS simulada: confirma el token apenas lo recibe."""

    def __init__(self, notificador, mac):
        self.notificador, self.mac, self.token = notificador, mac, None

    def enviar(self, mensaje):
        self.token = mensaje["token"]
        self.notificador.confirmar(self.mac)
        return True


class _ConexionOperando:
    """Conexion WS simulada de una matera ya autenticada: guarda lo que el backend le envia."""

    def __init__(self):
        self.recibidos: list[dict] = []

    def enviar(self, mensaje):
        self.recibidos.append(mensaje)
        return True


class ApiTest(unittest.TestCase):
    fuente = "csv"

    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        config = Configuracion(
            fuente_especies=self.fuente,
            ruta_bd=self.carpeta / "prueba.db",
            jwt_secreto="secreto-de-pruebas-con-longitud-suficiente",
            rondas_bcrypt=4,
            limite_intentos=1000,
            admin_usuario="admin",
            admin_email="admin@matera.co",
            admin_password="admin-secreto",
        )
        self.app = create_app(config)
        self.cliente = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.carpeta, ignore_errors=True)

    # ------------------------------------------------ auxiliares

    def sesion(self, nombre: str) -> dict:
        self.cliente.post("/api/v1/auth/registro", json={
            "nombre": nombre, "email": f"{nombre}@correo.com", "password": "clave-segura",
        })
        respuesta = self.cliente.post("/api/v1/auth/login", json={"usuario": nombre, "password": "clave-segura"})
        return {"Authorization": f"Bearer {respuesta.get_json()['token']}"}

    def admin(self) -> dict:
        token = self.cliente.post(
            "/api/v1/auth/login", json={"usuario": "admin", "password": "admin-secreto"}
        ).get_json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def crear_planta(self, cabeceras) -> int:
        respuesta = self.cliente.post(
            "/api/v1/plantas", json={"apodo": "Sanse", "especie": "sansevieria"}, headers=cabeceras
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        return respuesta.get_json()["id"]

    def vincular(self, cabeceras, planta_id) -> str:
        extensiones = self.app.extensions["matera"]
        extensiones["emparejar"].anunciar(MAC)
        dispositivo = _DispositivoFalso(extensiones["notificador_dispositivo"], MAC)
        extensiones["notificador_dispositivo"].registrar(MAC, dispositivo)
        respuesta = self.cliente.post(
            f"/api/v1/plantas/{planta_id}/dispositivo", json={"mac": MAC}, headers=cabeceras
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        return dispositivo.token

    # ------------------------------------------------ pruebas

    def test_catalogo_y_diagnostico_ad_hoc_sin_sesion(self):
        especies = self.cliente.get("/api/v1/especies").get_json()["especies"]
        self.assertIn("sansevieria", [e["nombre"] for e in especies])
        respuesta = self.cliente.post("/api/v1/diagnosticos", json={"especie": "sansevieria", **OPTIMA})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["estado_global"], "SALUDABLE")
        self.assertIsNone(respuesta.get_json()["animo"])  # el diagnostico ad hoc no evalua el animo

    def test_errores_de_entrada_tienen_codigo_y_cuerpo_uniforme(self):
        casos = [
            ({"especie": "inexistente", **OPTIMA}, 404, "ESPECIE_DESCONOCIDA"),
            ({"especie": "sansevieria", "humedad": 40, "luz": 300}, 400, "PARAMETRO_AUSENTE"),
            ({"especie": "sansevieria", **OPTIMA, "luz": "abc"}, 400, "VALOR_NO_NUMERICO"),
            ({"especie": "sansevieria", **OPTIMA, "humedad": 150}, 422, "VALOR_FUERA_DE_RANGO_FISICO"),
        ]
        for cuerpo, status, codigo in casos:
            with self.subTest(codigo=codigo):
                respuesta = self.cliente.post("/api/v1/diagnosticos", json=cuerpo)
                self.assertEqual(respuesta.status_code, status)
                self.assertEqual(set(respuesta.get_json()), {"error", "mensaje", "detalle"})
                self.assertEqual(respuesta.get_json()["error"], codigo)

    def test_plantas_exigen_jwt(self):
        self.assertEqual(self.cliente.get("/api/v1/plantas").status_code, 401)
        self.assertEqual(
            self.cliente.get("/api/v1/plantas", headers={"Authorization": "Bearer basura"}).status_code, 401
        )

    def test_acceso_a_planta_ajena_falla(self):
        ana, beto = self.sesion("ana"), self.sesion("beto")
        planta_id = self.crear_planta(ana)
        self.assertEqual(self.cliente.get(f"/api/v1/plantas/{planta_id}", headers=ana).status_code, 200)
        self.assertEqual(self.cliente.get(f"/api/v1/plantas/{planta_id}", headers=beto).status_code, 404)
        self.assertEqual(
            self.cliente.get(f"/api/v1/plantas/{planta_id}/lecturas", headers=beto).status_code, 404
        )

    def test_flujo_completo_dispositivo_lecturas_e_historial(self):
        ana = self.sesion("ana")
        planta_id = self.crear_planta(ana)
        token = self.vincular(ana, planta_id)
        self.assertGreaterEqual(len(token), 43)  # 256 bits en base64url

        url = f"/api/v1/dispositivos/{MAC}/lecturas"
        ok = self.cliente.post(url, json={**OPTIMA, "humedad": 10}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(ok.status_code, 201, ok.get_json())
        self.assertEqual(ok.get_json()["diagnostico"]["estado_global"], "EN_RIESGO")
        self.assertEqual(ok.get_json()["animo"], "SEDIENTA")
        self.assertEqual(ok.get_json()["diagnostico"]["animo"], "SEDIENTA")

        malo = self.cliente.post(url, json=OPTIMA, headers={"Authorization": "Bearer token-falso"})
        self.assertEqual(malo.status_code, 401)

        detalle = self.cliente.get(f"/api/v1/plantas/{planta_id}", headers=ana).get_json()
        self.assertEqual(detalle["estado_actual"], "EN_RIESGO")
        self.assertEqual(detalle["dispositivo"]["mac"], MAC)
        historial = self.cliente.get(f"/api/v1/plantas/{planta_id}/lecturas", headers=ana).get_json()
        self.assertEqual(len(historial["lecturas"]), 1)
        self.assertEqual(historial["lecturas"][0]["animo"], "SEDIENTA")  # leido de la BD
        vacio = self.cliente.get(
            f"/api/v1/plantas/{planta_id}/lecturas?desde=2099-01-01T00:00:00Z", headers=ana
        ).get_json()
        self.assertEqual(vacio["lecturas"], [])

        self.assertEqual(self.cliente.delete(f"/api/v1/plantas/{planta_id}/dispositivo", headers=ana).status_code, 204)
        revocado = self.cliente.post(url, json=OPTIMA, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(revocado.status_code, 401)

    def test_respuesta_ws_diagnostico_incluye_animo_y_la_matera_recibe_mascota(self):
        ana = self.sesion("ana")
        token = self.vincular(ana, self.crear_planta(ana))
        adaptador = self.app.extensions["matera"]["ws_dispositivos"]
        conexion = _ConexionOperando()
        sesion = {"mac_emparejando": None, "dispositivo_id": None, "mac": None}
        with self.app.test_request_context():
            autenticado = adaptador._procesar(
                conexion, sesion, json.dumps({"tipo": "autenticar", "mac": MAC, "token": token})
            )
            respuesta = adaptador._procesar(
                conexion, sesion, json.dumps({"tipo": "lectura", **OPTIMA, "temperatura": 40})
            )
        self.assertEqual(autenticado, {"tipo": "autenticado"})
        self.assertEqual(respuesta["tipo"], "diagnostico")
        self.assertEqual(respuesta["animo"], "ACALORADA")
        self.assertEqual(conexion.recibidos, [{"tipo": "mascota", "animo": "ACALORADA"}])

    def test_los_websockets_hacen_ping_para_cerrar_conexiones_muertas(self):
        self.assertEqual(self.app.config["SOCK_SERVER_OPTIONS"]["ping_interval"], 25)

    def test_lectura_por_post_sin_matera_conectada_igual_se_guarda(self):
        ana = self.sesion("ana")
        token = self.vincular(ana, self.crear_planta(ana))  # no hay conexion "operando" registrada
        respuesta = self.cliente.post(
            f"/api/v1/dispositivos/{MAC}/lecturas", json=OPTIMA, headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.get_json())
        self.assertEqual(respuesta.get_json()["animo"], "FELIZ")

    def test_vincular_sin_emparejamiento_responde_uniforme(self):
        ana = self.sesion("ana")
        planta_id = self.crear_planta(ana)
        respuesta = self.cliente.post(
            f"/api/v1/plantas/{planta_id}/dispositivo", json={"mac": "11:22:33:44:55:66"}, headers=ana
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_invitacion_de_un_solo_uso(self):
        ana, beto, carla = self.sesion("ana"), self.sesion("beto"), self.sesion("carla")
        planta_id = self.crear_planta(ana)
        token = self.cliente.post(f"/api/v1/plantas/{planta_id}/invitaciones", headers=ana).get_json()["token"]
        self.assertEqual(
            self.cliente.post("/api/v1/invitaciones/canje", json={"token": token}, headers=beto).status_code, 200
        )
        self.assertEqual(self.cliente.get(f"/api/v1/plantas/{planta_id}", headers=beto).get_json()["vinculo"], "CUIDADOR")
        self.assertEqual(
            self.cliente.post("/api/v1/invitaciones/canje", json={"token": token}, headers=carla).status_code, 410
        )
        self.assertEqual(self.cliente.patch(
            f"/api/v1/plantas/{planta_id}", json={"apodo": "x"}, headers=beto).status_code, 403)

    def test_admin_gestiona_cuentas_y_usuario_no(self):
        ana = self.sesion("ana")
        self.assertEqual(self.cliente.get("/api/v1/admin/usuarios", headers=ana).status_code, 403)
        usuarios = self.cliente.get("/api/v1/admin/usuarios", headers=self.admin()).get_json()["usuarios"]
        ana_id = next(u["id"] for u in usuarios if u["nombre"] == "ana")
        self.cliente.patch(f"/api/v1/admin/usuarios/{ana_id}", json={"activo": False}, headers=self.admin())
        login = self.cliente.post("/api/v1/auth/login", json={"usuario": "ana", "password": "clave-segura"})
        self.assertEqual(login.status_code, 401)

    def test_login_no_revela_si_el_usuario_existe(self):
        self.sesion("ana")
        a = self.cliente.post("/api/v1/auth/login", json={"usuario": "ana", "password": "mala-clave"})
        b = self.cliente.post("/api/v1/auth/login", json={"usuario": "nadie", "password": "mala-clave"})
        self.assertEqual((a.status_code, a.get_json()), (b.status_code, b.get_json()))

    def test_la_contrasena_no_se_guarda_en_texto_plano(self):
        self.sesion("ana")
        for archivo in self.carpeta.iterdir():  # incluye el -wal de SQLite
            self.assertNotIn(b"clave-segura", archivo.read_bytes())


class ApiConTablaEnBdTest(ApiTest):
    """Las mismas pruebas con la tabla de referencia en SQLite (RA15): solo cambia la configuracion."""

    fuente = "sqlite"

    def test_especie_aprobada_por_admin_queda_disponible(self):
        ana = self.sesion("ana")
        solicitud = self.cliente.post(
            "/api/v1/especies/solicitudes", json={"nombre": "Monstera", "justificacion": "la tengo"}, headers=ana
        ).get_json()
        especie = {
            "nombre": "monstera",
            "nombre_cientifico": "Monstera deliciosa",
            "rangos": {
                "humedad": {"minimo": 50, "maximo": 80},
                "luz": {"minimo": 500, "maximo": 2500},
                "temperatura": {"minimo": 18, "maximo": 30},
            },
        }
        respuesta = self.cliente.post(
            f"/api/v1/especies/solicitudes/{solicitud['id']}/aprobar", json=especie, headers=self.admin()
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        nombres = [e["nombre"] for e in self.cliente.get("/api/v1/especies").get_json()["especies"]]
        self.assertIn("monstera", nombres)


# Esquema anterior a diagnostico.animo y regla_animo (solo las tablas que la prueba llena).
ESQUEMA_VIEJO = """
CREATE TABLE parametro (
    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL, unidad TEXT NOT NULL,
    min_fisico REAL NOT NULL, max_fisico REAL NOT NULL
);
CREATE TABLE especie (
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL, nombre_cientifico TEXT,
    fuente TEXT NOT NULL, activa INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE planta (
    id INTEGER PRIMARY KEY AUTOINCREMENT, especie_id INTEGER NOT NULL REFERENCES especie (id),
    apodo TEXT NOT NULL, creada_en TEXT NOT NULL, activa INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE medicion (
    id INTEGER PRIMARY KEY AUTOINCREMENT, planta_id INTEGER NOT NULL REFERENCES planta (id),
    dispositivo_id INTEGER NULL, tomada_en TEXT NOT NULL,
    origen TEXT NOT NULL CHECK (origen IN ('HTTP', 'WS'))
);
CREATE TABLE diagnostico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, medicion_id INTEGER UNIQUE NOT NULL REFERENCES medicion (id),
    estado_global TEXT NOT NULL CHECK (estado_global IN ('SALUDABLE', 'EN_RIESGO', 'CRITICO')),
    evaluado_en TEXT NOT NULL
);
INSERT INTO especie (nombre, fuente) VALUES ('sansevieria', 'prueba');
INSERT INTO planta (especie_id, apodo, creada_en) VALUES (1, 'Vieja', '2026-01-01T00:00:00.000000+00:00');
INSERT INTO medicion (planta_id, tomada_en, origen) VALUES (1, '2026-01-01T00:00:00.000000+00:00', 'WS');
INSERT INTO diagnostico (medicion_id, estado_global, evaluado_en)
    VALUES (1, 'SALUDABLE', '2026-01-01T00:00:00.000000+00:00');
"""


class BaseDeDatosAnimoTest(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp())
        self.ruta = self.carpeta / "matera.db"

    def tearDown(self):
        shutil.rmtree(self.carpeta, ignore_errors=True)

    def test_reglas_animo_bd_lee_los_datos_iniciales(self):
        bd = BaseDatosSqlite(self.ruta)
        bd.inicializar(PARAMETROS, [])
        bd.inicializar(PARAMETROS, [])  # idempotente: no duplica reglas
        self.assertEqual(ReglasAnimoBD(bd).listar(), REGLAS_ANIMO)

    def test_la_migracion_no_rompe_una_bd_con_el_esquema_viejo(self):
        conexion = sqlite3.connect(self.ruta)
        conexion.executescript(ESQUEMA_VIEJO)
        conexion.close()

        bd = BaseDatosSqlite(self.ruta)
        bd.inicializar(PARAMETROS, [])
        bd.inicializar(PARAMETROS, [])  # la segunda vez no intenta agregar la columna de nuevo

        with bd.lectura() as c:
            columnas = {fila["name"] for fila in c.execute("PRAGMA table_info(diagnostico)")}
        self.assertIn("animo", columnas)
        vieja = RepoLecturas(bd).ultima(1)
        self.assertEqual(vieja.diagnostico.animo, Animo.FELIZ)
        self.assertEqual(len(ReglasAnimoBD(bd).listar()), 3)


if __name__ == "__main__":
    unittest.main()
