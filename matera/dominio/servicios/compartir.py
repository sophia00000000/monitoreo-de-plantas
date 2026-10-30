from datetime import timedelta

from matera.dominio.errores import Conflicto, InvitacionNoDisponible
from matera.dominio.modelo import (
    EntradaAuditoria,
    EstadoInvitacion,
    EventoAuditoria,
    Identidad,
    Invitacion,
    InvitacionEmitida,
    Planta,
)
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.puertos.entrada import CompartirPlantaPort
from matera.dominio.puertos.salida import (
    AuditoriaPort,
    GeneradorTokenPort,
    RelojPort,
    RepositorioInvitacionesPort,
    RepositorioPlantasPort,
)

MENSAJE_NO_DISPONIBLE = "La invitacion no es valida o ya no esta disponible."


class CompartirPlantaService(CompartirPlantaPort):
    """Invitaciones de un solo uso que expiran (RF15, RA20, RA21).

    El dominio solo conoce el token; dibujar el QR es trabajo del front.
    """

    def __init__(
        self,
        plantas: RepositorioPlantasPort,
        invitaciones: RepositorioInvitacionesPort,
        politica: PoliticaPropiedad,
        generador: GeneradorTokenPort,
        reloj: RelojPort,
        auditoria: AuditoriaPort,
        duracion: timedelta = timedelta(hours=24),
    ):
        self._plantas = plantas
        self._invitaciones = invitaciones
        self._politica = politica
        self._generador = generador
        self._reloj = reloj
        self._auditoria = auditoria
        self._duracion = duracion

    def generar_invitacion(self, identidad: Identidad, planta_id: int) -> InvitacionEmitida:
        self._politica.exigir_compartir(identidad, planta_id)
        ahora = self._reloj.ahora()
        token = self._generador.generar()
        invitacion = self._invitaciones.crear(Invitacion(
            id=None,
            planta_id=planta_id,
            creada_por=identidad.usuario_id,
            token_hash=token.hash,
            estado=EstadoInvitacion.PENDIENTE,
            expira_en=ahora + self._duracion,
            creada_en=ahora,
        ))
        return InvitacionEmitida(token=token.valor, planta_id=planta_id, expira_en=invitacion.expira_en)

    def canjear(self, identidad: Identidad, token: str) -> Planta:
        if not isinstance(token, str) or not token.strip():
            self._fallo(identidad, None)
        ahora = self._reloj.ahora()
        invitacion = self._invitaciones.por_hash(self._generador.hashear(token.strip()))
        if invitacion is None or invitacion.estado != EstadoInvitacion.PENDIENTE:
            self._fallo(identidad, invitacion)
        if invitacion.expira_en <= ahora:
            self._invitaciones.marcar_expirada(invitacion.id)
            self._fallo(identidad, invitacion)
        planta = self._plantas.obtener(invitacion.planta_id)
        if planta is None or not planta.activa:
            self._fallo(identidad, invitacion)
        if self._plantas.vinculo(planta.id, identidad.usuario_id) is not None:
            raise Conflicto("Ya estas vinculado a esta planta.")
        if not self._invitaciones.consumir_y_vincular(invitacion.id, identidad.usuario_id, ahora):
            self._fallo(identidad, invitacion)
        self._auditoria.registrar(EntradaAuditoria(
            evento=EventoAuditoria.CANJE,
            ocurrido_en=ahora,
            usuario_id=identidad.usuario_id,
            planta_id=planta.id,
        ))
        return planta

    def _fallo(self, identidad: Identidad, invitacion: Invitacion | None):
        """Respuesta uniforme (RA24): no distingue codigo inexistente, usado o vencido."""
        self._auditoria.registrar(EntradaAuditoria(
            evento=EventoAuditoria.INTENTO_FALLIDO,
            ocurrido_en=self._reloj.ahora(),
            usuario_id=identidad.usuario_id,
            planta_id=invitacion.planta_id if invitacion else None,
            detalle="canje de invitacion",
        ))
        raise InvitacionNoDisponible(MENSAJE_NO_DISPONIBLE)
