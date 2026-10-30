"""Emparejamiento, vinculacion y autenticacion de dispositivos (RF11, RF20, RF21, RA11, RA21, RA22)."""
from datetime import datetime

from matera.dominio.errores import (
    Conflicto,
    CredencialesInvalidas,
    DatosInvalidos,
    EntregaTokenFallida,
    RecursoNoEncontrado,
)
from matera.dominio.modelo import (
    VENTANA_EMPAREJAMIENTO,
    Dispositivo,
    EntradaAuditoria,
    EstadoDispositivo,
    EventoAuditoria,
    Identidad,
    normalizar_mac,
)
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.puertos.entrada import (
    AutenticarDispositivoPort,
    EmparejarDispositivoPort,
    VincularDispositivoPort,
)
from matera.dominio.puertos.salida import (
    AuditoriaPort,
    GeneradorTokenPort,
    NotificadorDispositivoPort,
    RelojPort,
    RepositorioDispositivosPort,
)

MENSAJE_NO_DISPONIBLE = "No hay un dispositivo en emparejamiento con esa MAC."


class VincularDispositivoService(VincularDispositivoPort, EmparejarDispositivoPort):
    def __init__(
        self,
        dispositivos: RepositorioDispositivosPort,
        politica: PoliticaPropiedad,
        generador: GeneradorTokenPort,
        notificador: NotificadorDispositivoPort,
        reloj: RelojPort,
        auditoria: AuditoriaPort,
    ):
        self._dispositivos = dispositivos
        self._politica = politica
        self._generador = generador
        self._notificador = notificador
        self._reloj = reloj
        self._auditoria = auditoria

    # ------------------------------------------------ lado dispositivo (RF20)

    def anunciar(self, mac: str) -> datetime:
        mac = normalizar_mac(mac)
        ahora = self._reloj.ahora()
        dispositivo = self._dispositivos.por_mac(mac)
        if dispositivo is None:
            dispositivo = self._dispositivos.registrar(Dispositivo(
                id=None,
                mac=mac,
                estado=EstadoDispositivo.SIN_VINCULAR,
                planta_id=None,
                token_hash=None,
                ventana_expira_en=None,
                registrado_en=ahora,
            ))
        if dispositivo.estado == EstadoDispositivo.VINCULADO:
            raise Conflicto("El dispositivo ya esta vinculado a una planta.")
        ventana_abierta = (
            dispositivo.estado == EstadoDispositivo.EMPAREJANDO
            and dispositivo.ventana_expira_en is not None
            and dispositivo.ventana_expira_en > ahora
        )
        if ventana_abierta:
            raise Conflicto("Ya hay una conexion de emparejamiento abierta para esta MAC.")
        dispositivo.estado = EstadoDispositivo.EMPAREJANDO
        dispositivo.planta_id = None
        dispositivo.token_hash = None
        dispositivo.ventana_expira_en = ahora + VENTANA_EMPAREJAMIENTO
        self._dispositivos.guardar(dispositivo)
        self._auditar(EventoAuditoria.EMPAREJAMIENTO, dispositivo_id=dispositivo.id)
        return dispositivo.ventana_expira_en

    def cancelar(self, mac: str) -> None:
        try:
            mac = normalizar_mac(mac)
        except DatosInvalidos:
            return
        dispositivo = self._dispositivos.por_mac(mac)
        if dispositivo is not None and dispositivo.estado == EstadoDispositivo.EMPAREJANDO:
            dispositivo.estado = EstadoDispositivo.SIN_VINCULAR
            dispositivo.ventana_expira_en = None
            self._dispositivos.guardar(dispositivo)

    # ------------------------------------------------ lado usuario (RF11, RF21)

    def vincular(self, identidad: Identidad, planta_id: int, mac: str) -> Dispositivo:
        self._politica.exigir_gestionar(identidad, planta_id)
        if self._dispositivos.por_planta(planta_id) is not None:
            raise Conflicto("La planta ya tiene un dispositivo vinculado.")
        ahora = self._reloj.ahora()
        try:
            mac = normalizar_mac(mac)
        except DatosInvalidos:
            self._fallo_vinculacion(identidad, planta_id, None)
        dispositivo = self._dispositivos.por_mac(mac)
        disponible = (
            dispositivo is not None
            and dispositivo.estado == EstadoDispositivo.EMPAREJANDO
            and dispositivo.ventana_expira_en is not None
            and dispositivo.ventana_expira_en > ahora
        )
        if not disponible:
            self._fallo_vinculacion(identidad, planta_id, dispositivo)

        token = self._generador.generar()
        if not self._dispositivos.vincular_si_emparejando(dispositivo.id, planta_id, token.hash, ahora):
            self._fallo_vinculacion(identidad, planta_id, dispositivo)
        self._auditar(EventoAuditoria.VINCULACION, identidad.usuario_id, dispositivo.id, planta_id)

        try:
            entregado = self._notificador.entregar_token(mac, token.valor)
        except Exception:
            entregado = False
        if not entregado:
            self._dispositivos.revertir_vinculo(dispositivo.id)
            self._auditar(EventoAuditoria.VINCULACION_REVERTIDA, identidad.usuario_id, dispositivo.id, planta_id)
            raise EntregaTokenFallida(
                "No se pudo entregar el token al dispositivo; la vinculacion se revirtio. "
                "Vuelva a poner el dispositivo en emparejamiento."
            )
        return self._dispositivos.obtener(dispositivo.id)

    def desvincular(self, identidad: Identidad, planta_id: int) -> None:
        self._politica.exigir_gestionar(identidad, planta_id)
        dispositivo = self._dispositivos.por_planta(planta_id)
        if dispositivo is None:
            raise RecursoNoEncontrado("La planta no tiene un dispositivo vinculado.")
        self._dispositivos.revocar(dispositivo.id)
        self._auditar(EventoAuditoria.DESVINCULACION, identidad.usuario_id, dispositivo.id, planta_id)

    # ------------------------------------------------ auxiliares

    def _fallo_vinculacion(self, identidad: Identidad, planta_id: int, dispositivo: Dispositivo | None):
        """Respuesta uniforme: no revela si la MAC existe ni en que estado esta (RA24)."""
        self._auditar(
            EventoAuditoria.INTENTO_FALLIDO,
            identidad.usuario_id,
            dispositivo.id if dispositivo else None,
            planta_id,
            detalle="vinculacion",
        )
        raise RecursoNoEncontrado(MENSAJE_NO_DISPONIBLE)

    def _auditar(self, evento, usuario_id=None, dispositivo_id=None, planta_id=None, detalle=None):
        self._auditoria.registrar(EntradaAuditoria(
            evento=evento,
            ocurrido_en=self._reloj.ahora(),
            usuario_id=usuario_id,
            dispositivo_id=dispositivo_id,
            planta_id=planta_id,
            detalle=detalle,
        ))


class AutenticacionDispositivoService(AutenticarDispositivoPort):
    def __init__(
        self,
        dispositivos: RepositorioDispositivosPort,
        generador: GeneradorTokenPort,
        reloj: RelojPort,
        auditoria: AuditoriaPort,
    ):
        self._dispositivos = dispositivos
        self._generador = generador
        self._reloj = reloj
        self._auditoria = auditoria

    def autenticar(self, mac: str, token: str) -> int:
        dispositivo = None
        try:
            dispositivo = self._dispositivos.por_mac(normalizar_mac(mac))
        except DatosInvalidos:
            pass
        valido = (
            dispositivo is not None
            and dispositivo.estado == EstadoDispositivo.VINCULADO
            and dispositivo.token_hash is not None
            and isinstance(token, str)
            and self._generador.coincide(token, dispositivo.token_hash)
        )
        if not valido:
            self._auditoria.registrar(EntradaAuditoria(
                evento=EventoAuditoria.INTENTO_FALLIDO,
                ocurrido_en=self._reloj.ahora(),
                dispositivo_id=dispositivo.id if dispositivo else None,
                detalle="autenticacion de dispositivo",
            ))
            raise CredencialesInvalidas("Credenciales de dispositivo invalidas.")
        return dispositivo.id
