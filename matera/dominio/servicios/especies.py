from dataclasses import replace

from matera.dominio.errores import Conflicto, DatosInvalidos, RecursoNoEncontrado
from matera.dominio.modelo import (
    Especie,
    EstadoSolicitud,
    Identidad,
    SolicitudEspecie,
    normalizar_especie,
)
from matera.dominio.politica_propiedad import exigir_admin
from matera.dominio.puertos.entrada import GestionarEspeciesPort
from matera.dominio.puertos.salida import RelojPort, RepositorioEspeciesPort
from matera.dominio.validador import validar_especie


class EspeciesService(GestionarEspeciesPort):
    """Solicitudes de especie (RF16) y gestion de la tabla de referencia por el admin (RF17)."""

    def __init__(self, especies: RepositorioEspeciesPort, reloj: RelojPort):
        self._especies = especies
        self._reloj = reloj

    def solicitar(self, identidad: Identidad, nombre: str, justificacion: str) -> SolicitudEspecie:
        if not isinstance(nombre, str) or not 2 <= len(nombre.strip()) <= 80:
            raise DatosInvalidos("El nombre propuesto debe tener entre 2 y 80 caracteres.", campo="nombre")
        if self._especies.existe(normalizar_especie(nombre)):
            raise Conflicto("La especie ya esta soportada.")
        return self._especies.crear_solicitud(SolicitudEspecie(
            id=None,
            usuario_id=identidad.usuario_id,
            nombre_propuesto=nombre.strip(),
            justificacion=(justificacion or "").strip()[:500],
            estado=EstadoSolicitud.PENDIENTE,
            creada_en=self._reloj.ahora(),
        ))

    def listar_solicitudes(self, identidad: Identidad, estado: str | None) -> list[SolicitudEspecie]:
        if estado is not None and estado not in EstadoSolicitud.__members__:
            raise DatosInvalidos("Estado de solicitud no valido.", campo="estado")
        usuario_id = None if identidad.es_admin else identidad.usuario_id
        return self._especies.listar_solicitudes(usuario_id, estado)

    def aprobar(self, identidad: Identidad, solicitud_id: int, especie: Especie) -> SolicitudEspecie:
        exigir_admin(identidad)
        solicitud = self._pendiente(solicitud_id)
        guardada = self.guardar_especie(identidad, especie)
        return self._resolver(identidad, solicitud, EstadoSolicitud.APROBADA, guardada.id)

    def rechazar(self, identidad: Identidad, solicitud_id: int) -> SolicitudEspecie:
        exigir_admin(identidad)
        solicitud = self._pendiente(solicitud_id)
        return self._resolver(identidad, solicitud, EstadoSolicitud.RECHAZADA, None)

    def guardar_especie(self, identidad: Identidad, especie: Especie) -> Especie:
        exigir_admin(identidad)
        especie = replace(especie, nombre=normalizar_especie(especie.nombre), activa=True)
        validar_especie(especie)
        return self._especies.guardar_especie(especie)

    def desactivar_especie(self, identidad: Identidad, nombre: str) -> None:
        exigir_admin(identidad)
        if not self._especies.desactivar_especie(normalizar_especie(nombre or "")):
            raise RecursoNoEncontrado("La especie no existe.", especie=nombre)

    def _pendiente(self, solicitud_id: int) -> SolicitudEspecie:
        solicitud = self._especies.obtener_solicitud(solicitud_id)
        if solicitud is None:
            raise RecursoNoEncontrado("La solicitud no existe.", solicitud_id=solicitud_id)
        if solicitud.estado != EstadoSolicitud.PENDIENTE:
            raise Conflicto("La solicitud ya fue resuelta.")
        return solicitud

    def _resolver(self, identidad, solicitud, estado, especie_id) -> SolicitudEspecie:
        solicitud.estado = estado
        solicitud.resuelta_por = identidad.usuario_id
        solicitud.resuelta_en = self._reloj.ahora()
        solicitud.especie_id = especie_id
        if not self._especies.resolver_solicitud(solicitud):
            raise Conflicto("La solicitud ya fue resuelta.")
        return solicitud
