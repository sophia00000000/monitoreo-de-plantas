"""Regla de propiedad: quien puede hacer que sobre una planta (tabla de roles del documento)."""
from matera.dominio.errores import PermisoDenegado, RecursoNoEncontrado
from matera.dominio.modelo import (
    EntradaAuditoria,
    EventoAuditoria,
    Identidad,
    Planta,
    TipoVinculo,
)
from matera.dominio.puertos.salida import AuditoriaPort, RelojPort, RepositorioPlantasPort


def exigir_admin(identidad: Identidad) -> None:
    if not identidad.es_admin:
        raise PermisoDenegado("Esta operacion es solo para administradores.")


class PoliticaPropiedad:
    """Calcula Propietario/Cuidador a partir de vinculo_planta y decide permisos.

    - Sin vinculo y sin ser admin: 404 (no revela que la planta existe).
    - Con vinculo pero sin permiso para la operacion: 403.
    - Admin sobre una planta ajena: permitido solo donde la tabla lo dice, y queda auditado (RA26).
    """

    def __init__(self, plantas: RepositorioPlantasPort, auditoria: AuditoriaPort, reloj: RelojPort):
        self._plantas = plantas
        self._auditoria = auditoria
        self._reloj = reloj

    def exigir_ver(self, identidad: Identidad, planta_id: int) -> Planta:
        """Ver estado e historial: propietario, cuidador o admin."""
        return self._exigir(identidad, planta_id, {TipoVinculo.PROPIETARIO, TipoVinculo.CUIDADOR}, True)

    def exigir_gestionar(self, identidad: Identidad, planta_id: int) -> Planta:
        """Editar, eliminar, vincular y desvincular dispositivo: propietario o admin."""
        return self._exigir(identidad, planta_id, {TipoVinculo.PROPIETARIO}, True)

    def exigir_compartir(self, identidad: Identidad, planta_id: int) -> Planta:
        """Generar QR de invitacion: solo el propietario."""
        return self._exigir(identidad, planta_id, {TipoVinculo.PROPIETARIO}, False)

    def _exigir(
        self,
        identidad: Identidad,
        planta_id: int,
        permitidos: set[TipoVinculo],
        admin_permitido: bool,
    ) -> Planta:
        planta = self._plantas.obtener(planta_id)
        if planta is None or not planta.activa:
            raise RecursoNoEncontrado("La planta no existe.", planta_id=planta_id)
        vinculo = self._plantas.vinculo(planta_id, identidad.usuario_id)
        if vinculo in permitidos:
            return planta
        if identidad.es_admin and admin_permitido:
            if vinculo is None:
                self._auditoria.registrar(EntradaAuditoria(
                    evento=EventoAuditoria.ACCESO_ADMIN,
                    ocurrido_en=self._reloj.ahora(),
                    usuario_id=identidad.usuario_id,
                    planta_id=planta_id,
                ))
            return planta
        if vinculo is None:
            raise RecursoNoEncontrado("La planta no existe.", planta_id=planta_id)
        raise PermisoDenegado("No tienes permiso para esta operacion sobre la planta.", planta_id=planta_id)
