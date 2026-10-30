"""Pruebas de integracion de los adaptadores: Flask + SQLite en un archivo temporal.

No son pruebas del dominio (esas estan en test_dominio.py); verifican que la traduccion HTTP,
la persistencia y la composicion funcionen juntas.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from matera.app import create_app
from matera.config import Configuracion

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

        malo = self.cliente.post(url, json=OPTIMA, headers={"Authorization": "Bearer token-falso"})
        self.assertEqual(malo.status_code, 401)

        detalle = self.cliente.get(f"/api/v1/plantas/{planta_id}", headers=ana).get_json()
        self.assertEqual(detalle["estado_actual"], "EN_RIESGO")
        self.assertEqual(detalle["dispositivo"]["mac"], MAC)
        historial = self.cliente.get(f"/api/v1/plantas/{planta_id}/lecturas", headers=ana).get_json()
        self.assertEqual(len(historial["lecturas"]), 1)
        vacio = self.cliente.get(
            f"/api/v1/plantas/{planta_id}/lecturas?desde=2099-01-01T00:00:00Z", headers=ana
        ).get_json()
        self.assertEqual(vacio["lecturas"], [])

        self.assertEqual(self.cliente.delete(f"/api/v1/plantas/{planta_id}/dispositivo", headers=ana).status_code, 204)
        revocado = self.cliente.post(url, json=OPTIMA, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(revocado.status_code, 401)

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


if __name__ == "__main__":
    unittest.main()
