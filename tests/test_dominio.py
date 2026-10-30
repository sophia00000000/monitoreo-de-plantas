"""Pruebas unitarias del dominio con dobles de los puertos de salida (RA19).

No levantan Flask, no leen archivos y no usan base de datos.
"""
import unittest
from datetime import timedelta

from matera.dominio.errores import (
    Conflicto,
    CredencialesInvalidas,
    DatosInvalidos,
    EntregaTokenFallida,
    EspecieDesconocida,
    InvitacionNoDisponible,
    ParametroAusente,
    PermisoDenegado,
    RecursoNoEncontrado,
    ValorFueraDeRangoFisico,
    ValorNoNumerico,
)
from matera.dominio.modelo import (
    Especie,
    EstadoDispositivo,
    EstadoGlobal,
    EstadoParametro,
    Identidad,
    Lectura,
    OrigenLectura,
    Rango,
    Rol,
    TipoVinculo,
    normalizar_mac,
)
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.servicios.autenticacion import AutenticacionService
from matera.dominio.servicios.catalogo import CatalogoService
from matera.dominio.servicios.compartir import CompartirPlantaService
from matera.dominio.servicios.consulta_planta import ConsultaPlantaService
from matera.dominio.servicios.cuentas import CuentasService
from matera.dominio.servicios.dispositivos import (
    AutenticacionDispositivoService,
    VincularDispositivoService,
)
from matera.dominio.servicios.especies import EspeciesService
from matera.dominio.servicios.plantas import PlantasService
from matera.dominio.servicios.registrar_lectura import RegistrarLecturaService
from matera.dominio.validador import Evaluador
from tests.dobles import (
    AdapterEnMemoria,
    AuditoriaEnMemoria,
    DispositivosEnMemoria,
    EmisorJwtFalso,
    GeneradorTokenFalso,
    HasherFalso,
    HistorialEnMemoria,
    InvitacionesEnMemoria,
    NotificadorDispositivoFalso,
    NotificadorEstadoFalso,
    PlantasEnMemoria,
    RelojFijo,
    UsuariosEnMemoria,
)

MAC = "AA:BB:CC:DD:EE:01"
OPTIMA = {"humedad": 40, "luz": 300, "temperatura": 22}


class Escenario:
    """Arma todos los casos de uso con dobles, como lo haria create_app con adaptadores reales."""

    def __init__(self):
        self.reloj = RelojFijo()
        self.rangos = AdapterEnMemoria()
        self.usuarios = UsuariosEnMemoria()
        self.plantas = PlantasEnMemoria()
        self.dispositivos = DispositivosEnMemoria()
        self.invitaciones = InvitacionesEnMemoria(self.plantas)
        self.historial = HistorialEnMemoria()
        self.auditoria = AuditoriaEnMemoria()
        self.generador = GeneradorTokenFalso()
        self.notificador_dispositivo = NotificadorDispositivoFalso()
        self.notificador_estado = NotificadorEstadoFalso()

        self.politica = PoliticaPropiedad(self.plantas, self.auditoria, self.reloj)
        self.evaluador = Evaluador(self.rangos)
        self.auth = AutenticacionService(self.usuarios, HasherFalso(), EmisorJwtFalso(), self.reloj, self.auditoria)
        self.gestion = PlantasService(
            self.plantas, self.rangos, self.dispositivos, self.politica, self.reloj, self.auditoria
        )
        self.consulta = ConsultaPlantaService(self.plantas, self.dispositivos, self.historial, self.politica)
        self.vinculacion = VincularDispositivoService(
            self.dispositivos, self.politica, self.generador, self.notificador_dispositivo, self.reloj, self.auditoria
        )
        self.auth_dispositivo = AutenticacionDispositivoService(
            self.dispositivos, self.generador, self.reloj, self.auditoria
        )
        self.lecturas = RegistrarLecturaService(
            self.dispositivos, self.plantas, self.evaluador, self.historial, self.notificador_estado, self.reloj
        )
        self.compartir = CompartirPlantaService(
            self.plantas, self.invitaciones, self.politica, self.generador, self.reloj, self.auditoria,
            duracion=timedelta(hours=1),
        )

        self.ana = Identidad(1, Rol.USUARIO)    # propietaria
        self.beto = Identidad(2, Rol.USUARIO)   # sin relacion / futuro cuidador
        self.admin = Identidad(3, Rol.ADMIN)

    def planta_de_ana(self):
        return self.gestion.crear(self.ana, "Mi sansevieria", "Sansevieria")

    def dispositivo_vinculado(self, planta_id: int) -> str:
        self.vinculacion.anunciar(MAC)
        self.vinculacion.vincular(self.ana, planta_id, MAC)
        return self.notificador_dispositivo.entregados[-1][1]


# ====================================================================== diagnostico (RF1-RF4, RF6, RF7)

class EvaluadorTest(unittest.TestCase):
    def setUp(self):
        self.evaluador = Evaluador(AdapterEnMemoria())

    def test_lectura_en_rango_es_saludable(self):
        diagnostico = self.evaluador.diagnosticar("sansevieria", Lectura(OPTIMA))
        self.assertEqual(diagnostico.estado_global, EstadoGlobal.SALUDABLE)
        self.assertTrue(all(p.estado == EstadoParametro.OPTIMO for p in diagnostico.parametros))
        self.assertEqual(diagnostico.recomendaciones, [])

    def test_un_parametro_fuera_de_rango_queda_en_riesgo_con_recomendacion(self):
        diagnostico = self.evaluador.diagnosticar("sansevieria", Lectura({**OPTIMA, "humedad": 10}))
        self.assertEqual(diagnostico.estado_global, EstadoGlobal.EN_RIESGO)
        humedad = next(p for p in diagnostico.parametros if p.parametro == "humedad")
        self.assertEqual(humedad.estado, EstadoParametro.BAJO)
        self.assertEqual(len(diagnostico.recomendaciones), 1)

    def test_dos_parametros_fuera_de_rango_es_critico(self):
        diagnostico = self.evaluador.diagnosticar(
            "sansevieria", Lectura({"humedad": 90, "luz": 50, "temperatura": 22})
        )
        self.assertEqual(diagnostico.estado_global, EstadoGlobal.CRITICO)
        estados = {p.parametro: p.estado for p in diagnostico.parametros}
        self.assertEqual(estados["humedad"], EstadoParametro.ALTO)
        self.assertEqual(estados["luz"], EstadoParametro.BAJO)

    def test_limites_del_rango_son_optimos(self):
        diagnostico = self.evaluador.diagnosticar(
            "sansevieria", Lectura({"humedad": 30, "luz": 800, "temperatura": 18})
        )
        self.assertEqual(diagnostico.estado_global, EstadoGlobal.SALUDABLE)

    def test_especie_desconocida(self):
        with self.assertRaises(EspecieDesconocida):
            self.evaluador.diagnosticar("cactus_lunar", Lectura(OPTIMA))

    def test_parametro_ausente(self):
        with self.assertRaises(ParametroAusente):
            self.evaluador.diagnosticar("sansevieria", Lectura({"humedad": 40, "luz": 300}))

    def test_valor_no_numerico(self):
        with self.assertRaises(ValorNoNumerico):
            self.evaluador.diagnosticar("sansevieria", Lectura({**OPTIMA, "luz": "mucha"}))

    def test_valor_fuera_del_rango_fisico(self):
        with self.assertRaises(ValorFueraDeRangoFisico):
            self.evaluador.diagnosticar("sansevieria", Lectura({**OPTIMA, "humedad": 150}))

    def test_especie_se_busca_normalizada(self):
        diagnostico = self.evaluador.diagnosticar("  SANSEVIERIA ", Lectura(OPTIMA))
        self.assertEqual(diagnostico.especie, "sansevieria")

    def test_catalogo_lista_solo_especies_activas(self):
        rangos = AdapterEnMemoria()
        rangos.desactivar_especie("sansevieria")
        self.assertEqual(CatalogoService(rangos).listar_especies(), [])


# ====================================================================== cuentas (RF8, RF9, RF18)

class AutenticacionTest(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()

    def test_registro_guarda_hash_y_login_emite_token(self):
        usuario = self.e.auth.registrar("ana", "ana@correo.com", "secreta123")
        self.assertNotEqual(usuario.password_hash, "secreta123")
        sesion = self.e.auth.iniciar_sesion("ana", "secreta123")
        self.assertEqual(sesion.token, "jwt-1-USUARIO")

    def test_registro_duplicado_es_conflicto(self):
        self.e.auth.registrar("ana", "ana@correo.com", "secreta123")
        with self.assertRaises(Conflicto):
            self.e.auth.registrar("otra", "ana@correo.com", "secreta123")

    def test_contrasena_corta_es_rechazada(self):
        with self.assertRaises(DatosInvalidos):
            self.e.auth.registrar("ana", "ana@correo.com", "corta")

    def test_login_fallido_es_uniforme_y_se_audita(self):
        self.e.auth.registrar("ana", "ana@correo.com", "secreta123")
        with self.assertRaises(CredencialesInvalidas) as clave_mala:
            self.e.auth.iniciar_sesion("ana", "otra-clave")
        with self.assertRaises(CredencialesInvalidas) as usuario_inexistente:
            self.e.auth.iniciar_sesion("nadie", "otra-clave")
        self.assertEqual(clave_mala.exception.mensaje, usuario_inexistente.exception.mensaje)
        self.assertEqual(self.e.auditoria.eventos().count("INTENTO_FALLIDO"), 2)

    def test_cuenta_desactivada_no_inicia_sesion(self):
        self.e.auth.registrar("ana", "ana@correo.com", "secreta123")
        admin = self.e.auth.registrar("root", "root@correo.com", "secreta123", rol=Rol.ADMIN)
        CuentasService(self.e.usuarios).actualizar(Identidad(admin.id, Rol.ADMIN), 1, activo=False, rol=None)
        with self.assertRaises(CredencialesInvalidas):
            self.e.auth.iniciar_sesion("ana", "secreta123")

    def test_solo_el_admin_gestiona_cuentas(self):
        with self.assertRaises(PermisoDenegado):
            CuentasService(self.e.usuarios).listar(self.e.ana)


# ====================================================================== regla de propiedad

class PoliticaPropiedadTest(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.planta = self.e.planta_de_ana()

    def test_quien_crea_la_planta_queda_como_propietario(self):
        self.assertEqual(self.e.plantas.vinculo(self.planta.id, self.e.ana.usuario_id), TipoVinculo.PROPIETARIO)

    def test_propietario_ve_su_planta(self):
        detalle = self.e.consulta.detalle(self.e.ana, self.planta.id)
        self.assertEqual(detalle.planta.apodo, "Mi sansevieria")

    def test_usuario_ajeno_recibe_no_encontrado(self):
        with self.assertRaises(RecursoNoEncontrado):
            self.e.consulta.detalle(self.e.beto, self.planta.id)
        with self.assertRaises(RecursoNoEncontrado):
            self.e.consulta.historial(self.e.beto, self.planta.id, None, None, 10)

    def test_usuario_ajeno_no_ve_la_planta_en_su_lista(self):
        self.assertEqual(self.e.consulta.listar(self.e.beto), [])

    def test_cuidador_ve_pero_no_edita_ni_elimina(self):
        self.e.plantas.agregar_vinculo(self.planta.id, self.e.beto.usuario_id, TipoVinculo.CUIDADOR)
        self.e.consulta.detalle(self.e.beto, self.planta.id)
        with self.assertRaises(PermisoDenegado):
            self.e.gestion.editar(self.e.beto, self.planta.id, "otro nombre", None)
        with self.assertRaises(PermisoDenegado):
            self.e.gestion.eliminar(self.e.beto, self.planta.id)

    def test_admin_accede_a_planta_ajena_y_queda_auditado(self):
        self.e.consulta.detalle(self.e.admin, self.planta.id)
        self.assertIn("ACCESO_ADMIN", self.e.auditoria.eventos())

    def test_propietario_no_puede_desvincularse(self):
        with self.assertRaises(PermisoDenegado):
            self.e.gestion.desvincularse(self.e.ana, self.planta.id)

    def test_cuidador_puede_desvincularse(self):
        self.e.plantas.agregar_vinculo(self.planta.id, self.e.beto.usuario_id, TipoVinculo.CUIDADOR)
        self.e.gestion.desvincularse(self.e.beto, self.planta.id)
        self.assertIsNone(self.e.plantas.vinculo(self.planta.id, self.e.beto.usuario_id))

    def test_crear_planta_con_especie_no_soportada(self):
        with self.assertRaises(EspecieDesconocida):
            self.e.gestion.crear(self.e.ana, "Rara", "cactus_lunar")


# ====================================================================== dispositivos (RF11, RF12, RF20, RF21)

class DispositivosTest(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.planta = self.e.planta_de_ana()

    def test_anuncio_abre_ventana_de_diez_minutos(self):
        expira = self.e.vinculacion.anunciar("aa-bb-cc-dd-ee-01")
        self.assertEqual(expira - self.e.reloj.ahora(), timedelta(minutes=10))
        self.assertEqual(self.e.dispositivos.por_mac(MAC).estado, EstadoDispositivo.EMPAREJANDO)

    def test_solo_una_conexion_de_emparejamiento_por_mac(self):
        self.e.vinculacion.anunciar(MAC)
        with self.assertRaises(Conflicto):
            self.e.vinculacion.anunciar(MAC)

    def test_vincular_entrega_token_una_vez_y_guarda_solo_el_hash(self):
        token = self.e.dispositivo_vinculado(self.planta.id)
        dispositivo = self.e.dispositivos.por_mac(MAC)
        self.assertEqual(dispositivo.estado, EstadoDispositivo.VINCULADO)
        self.assertEqual(dispositivo.planta_id, self.planta.id)
        self.assertNotEqual(dispositivo.token_hash, token)
        self.assertEqual(len(self.e.notificador_dispositivo.entregados), 1)
        self.assertIn("VINCULACION", self.e.auditoria.eventos())

    def test_no_se_vincula_fuera_de_la_ventana(self):
        self.e.vinculacion.anunciar(MAC)
        self.e.reloj.avanzar(minutes=11)
        with self.assertRaises(RecursoNoEncontrado):
            self.e.vinculacion.vincular(self.e.ana, self.planta.id, MAC)

    def test_mac_inexistente_y_ventana_vencida_responden_igual(self):
        with self.assertRaises(RecursoNoEncontrado) as inexistente:
            self.e.vinculacion.vincular(self.e.ana, self.planta.id, "11:22:33:44:55:66")
        self.e.vinculacion.anunciar(MAC)
        self.e.reloj.avanzar(minutes=11)
        with self.assertRaises(RecursoNoEncontrado) as vencida:
            self.e.vinculacion.vincular(self.e.ana, self.planta.id, MAC)
        self.assertEqual(inexistente.exception.mensaje, vencida.exception.mensaje)

    def test_si_la_entrega_del_token_falla_se_revierte(self):
        self.e.notificador_dispositivo.exito = False
        self.e.vinculacion.anunciar(MAC)
        with self.assertRaises(EntregaTokenFallida):
            self.e.vinculacion.vincular(self.e.ana, self.planta.id, MAC)
        dispositivo = self.e.dispositivos.por_mac(MAC)
        self.assertEqual(dispositivo.estado, EstadoDispositivo.SIN_VINCULAR)
        self.assertIsNone(dispositivo.token_hash)
        self.assertIn("VINCULACION_REVERTIDA", self.e.auditoria.eventos())

    def test_cuidador_no_puede_vincular(self):
        self.e.plantas.agregar_vinculo(self.planta.id, self.e.beto.usuario_id, TipoVinculo.CUIDADOR)
        self.e.vinculacion.anunciar(MAC)
        with self.assertRaises(PermisoDenegado):
            self.e.vinculacion.vincular(self.e.beto, self.planta.id, MAC)

    def test_planta_con_dispositivo_no_acepta_otro(self):
        self.e.dispositivo_vinculado(self.planta.id)
        self.e.vinculacion.anunciar("AA:BB:CC:DD:EE:02")
        with self.assertRaises(Conflicto):
            self.e.vinculacion.vincular(self.e.ana, self.planta.id, "AA:BB:CC:DD:EE:02")

    def test_autenticacion_con_mac_y_token(self):
        token = self.e.dispositivo_vinculado(self.planta.id)
        dispositivo_id = self.e.auth_dispositivo.autenticar(MAC, token)
        self.assertEqual(dispositivo_id, self.e.dispositivos.por_mac(MAC).id)

    def test_token_invalido_es_rechazado_y_auditado(self):
        self.e.dispositivo_vinculado(self.planta.id)
        with self.assertRaises(CredencialesInvalidas):
            self.e.auth_dispositivo.autenticar(MAC, "token-falso")
        self.assertIn("INTENTO_FALLIDO", self.e.auditoria.eventos())

    def test_la_mac_sola_no_autentica(self):
        self.e.dispositivo_vinculado(self.planta.id)
        with self.assertRaises(CredencialesInvalidas):
            self.e.auth_dispositivo.autenticar(MAC, "")

    def test_desvincular_revoca_el_token_de_inmediato(self):
        token = self.e.dispositivo_vinculado(self.planta.id)
        self.e.vinculacion.desvincular(self.e.ana, self.planta.id)
        with self.assertRaises(CredencialesInvalidas):
            self.e.auth_dispositivo.autenticar(MAC, token)

    def test_eliminar_la_planta_revoca_el_token(self):
        token = self.e.dispositivo_vinculado(self.planta.id)
        self.e.gestion.eliminar(self.e.ana, self.planta.id)
        with self.assertRaises(CredencialesInvalidas):
            self.e.auth_dispositivo.autenticar(MAC, token)

    def test_cancelar_emparejamiento_devuelve_estado_inicial(self):
        self.e.vinculacion.anunciar(MAC)
        self.e.vinculacion.cancelar(MAC)
        self.assertEqual(self.e.dispositivos.por_mac(MAC).estado, EstadoDispositivo.SIN_VINCULAR)

    def test_mac_mal_formada(self):
        with self.assertRaises(DatosInvalidos):
            normalizar_mac("no-es-una-mac")


# ====================================================================== lecturas (RF12-RF14, RF19)

class RegistrarLecturaTest(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.planta = self.e.planta_de_ana()
        token = self.e.dispositivo_vinculado(self.planta.id)
        self.dispositivo_id = self.e.auth_dispositivo.autenticar(MAC, token)

    def test_lectura_se_evalua_guarda_y_publica(self):
        medicion = self.e.lecturas.registrar(
            self.dispositivo_id, Lectura({**OPTIMA, "temperatura": 40}), None, OrigenLectura.WS
        )
        self.assertEqual(medicion.diagnostico.estado_global, EstadoGlobal.EN_RIESGO)
        self.assertEqual(len(self.e.historial.mediciones), 1)
        self.assertEqual(self.e.notificador_estado.publicadas, [medicion])
        detalle = self.e.consulta.detalle(self.e.ana, self.planta.id)
        self.assertEqual(detalle.ultima_medicion, medicion)

    def test_lectura_invalida_no_se_guarda(self):
        with self.assertRaises(ValorFueraDeRangoFisico):
            self.e.lecturas.registrar(
                self.dispositivo_id, Lectura({**OPTIMA, "humedad": -5}), None, OrigenLectura.WS
            )
        self.assertEqual(self.e.historial.mediciones, [])

    def test_dispositivo_desvinculado_no_reporta(self):
        self.e.vinculacion.desvincular(self.e.ana, self.planta.id)
        with self.assertRaises(CredencialesInvalidas):
            self.e.lecturas.registrar(self.dispositivo_id, Lectura(OPTIMA), None, OrigenLectura.HTTP)

    def test_historial_filtra_por_fechas(self):
        inicio = self.e.reloj.ahora()
        for horas in range(5):
            self.e.lecturas.registrar(
                self.dispositivo_id, Lectura(OPTIMA), inicio - timedelta(hours=horas), OrigenLectura.WS
            )
        recientes = self.e.consulta.historial(
            self.e.ana, self.planta.id, inicio - timedelta(hours=2, minutes=30), None, 100
        )
        self.assertEqual(len(recientes), 3)
        self.assertGreaterEqual(recientes[0].tomada_en, recientes[-1].tomada_en)

    def test_marca_de_tiempo_futura_es_rechazada(self):
        with self.assertRaises(DatosInvalidos):
            self.e.lecturas.registrar(
                self.dispositivo_id, Lectura(OPTIMA), self.e.reloj.ahora() + timedelta(hours=1), OrigenLectura.WS
            )


# ====================================================================== invitaciones (RF15, RA20, RA21)

class CompartirTest(unittest.TestCase):
    def setUp(self):
        self.e = Escenario()
        self.planta = self.e.planta_de_ana()

    def test_canje_vincula_como_cuidador(self):
        invitacion = self.e.compartir.generar_invitacion(self.e.ana, self.planta.id)
        self.e.compartir.canjear(self.e.beto, invitacion.token)
        self.assertEqual(self.e.plantas.vinculo(self.planta.id, self.e.beto.usuario_id), TipoVinculo.CUIDADOR)
        self.assertIn("CANJE", self.e.auditoria.eventos())

    def test_invitacion_guarda_solo_el_hash(self):
        invitacion = self.e.compartir.generar_invitacion(self.e.ana, self.planta.id)
        guardada = next(iter(self.e.invitaciones.invitaciones.values()))
        self.assertNotEqual(guardada.token_hash, invitacion.token)

    def test_invitacion_es_de_un_solo_uso(self):
        invitacion = self.e.compartir.generar_invitacion(self.e.ana, self.planta.id)
        self.e.compartir.canjear(self.e.beto, invitacion.token)
        with self.assertRaises(InvitacionNoDisponible):
            self.e.compartir.canjear(Identidad(9, Rol.USUARIO), invitacion.token)

    def test_invitacion_expira(self):
        invitacion = self.e.compartir.generar_invitacion(self.e.ana, self.planta.id)
        self.e.reloj.avanzar(hours=2)
        with self.assertRaises(InvitacionNoDisponible):
            self.e.compartir.canjear(self.e.beto, invitacion.token)

    def test_token_inexistente(self):
        with self.assertRaises(InvitacionNoDisponible):
            self.e.compartir.canjear(self.e.beto, "no-existe")

    def test_propietario_no_canjea_su_propia_invitacion(self):
        invitacion = self.e.compartir.generar_invitacion(self.e.ana, self.planta.id)
        with self.assertRaises(Conflicto):
            self.e.compartir.canjear(self.e.ana, invitacion.token)

    def test_solo_el_propietario_genera_invitaciones(self):
        self.e.plantas.agregar_vinculo(self.planta.id, self.e.beto.usuario_id, TipoVinculo.CUIDADOR)
        with self.assertRaises(PermisoDenegado):
            self.e.compartir.generar_invitacion(self.e.beto, self.planta.id)
        with self.assertRaises(RecursoNoEncontrado):
            self.e.compartir.generar_invitacion(self.e.admin, self.planta.id)


# ====================================================================== especies (RF16, RF17)

class EspeciesTest(unittest.TestCase):
    def setUp(self):
        self.reloj = RelojFijo()
        self.repo = AdapterEnMemoria()
        self.servicio = EspeciesService(self.repo, self.reloj)
        self.usuario = Identidad(1, Rol.USUARIO)
        self.admin = Identidad(2, Rol.ADMIN)
        self.nueva = Especie(
            nombre="Monstera",
            nombre_cientifico="Monstera deliciosa",
            fuente="admin",
            rangos={"humedad": Rango(50, 80), "luz": Rango(500, 2500), "temperatura": Rango(18, 30)},
        )

    def test_usuario_solicita_y_admin_aprueba(self):
        solicitud = self.servicio.solicitar(self.usuario, "Monstera", "La tengo en casa")
        aprobada = self.servicio.aprobar(self.admin, solicitud.id, self.nueva)
        self.assertEqual(aprobada.estado.value, "APROBADA")
        self.assertIsNotNone(self.repo.obtener("monstera"))

    def test_usuario_no_aprueba(self):
        solicitud = self.servicio.solicitar(self.usuario, "Monstera", "")
        with self.assertRaises(PermisoDenegado):
            self.servicio.aprobar(self.usuario, solicitud.id, self.nueva)

    def test_solicitud_resuelta_no_se_resuelve_otra_vez(self):
        solicitud = self.servicio.solicitar(self.usuario, "Monstera", "")
        self.servicio.rechazar(self.admin, solicitud.id)
        with self.assertRaises(Conflicto):
            self.servicio.aprobar(self.admin, solicitud.id, self.nueva)

    def test_no_se_solicita_una_especie_soportada(self):
        with self.assertRaises(Conflicto):
            self.servicio.solicitar(self.usuario, "Sansevieria", "")

    def test_especie_con_rango_imposible_es_rechazada(self):
        imposible = Especie("x", "", "", {"humedad": Rango(50, 120), "luz": Rango(1, 2), "temperatura": Rango(1, 2)})
        with self.assertRaises(ValorFueraDeRangoFisico):
            self.servicio.guardar_especie(self.admin, imposible)


if __name__ == "__main__":
    unittest.main()
