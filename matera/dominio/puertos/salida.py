"""Puertos de salida: lo que el dominio necesita del exterior. Los implementan los adaptadores."""
from abc import ABC, abstractmethod
from datetime import datetime

from matera.dominio.modelo import (
    Dispositivo,
    EntradaAuditoria,
    Especie,
    Identidad,
    Invitacion,
    Medicion,
    Planta,
    SolicitudEspecie,
    TipoVinculo,
    TokenOpaco,
    Usuario,
)


# ---------------------------------------------------------------- catalogo (ISP: lectura y escritura separadas)

class ConsultarRangosPort(ABC):
    """Solo lectura: rangos de referencia de una especie y lista de especies activas."""

    @abstractmethod
    def obtener(self, nombre: str) -> Especie | None: ...

    @abstractmethod
    def listar(self) -> list[Especie]: ...


class RepositorioEspeciesPort(ABC):
    """Solo escritura y gestion de especies y solicitudes (admin)."""

    @abstractmethod
    def existe(self, nombre: str) -> bool: ...

    @abstractmethod
    def guardar_especie(self, especie: Especie) -> Especie: ...

    @abstractmethod
    def desactivar_especie(self, nombre: str) -> bool: ...

    @abstractmethod
    def crear_solicitud(self, solicitud: SolicitudEspecie) -> SolicitudEspecie: ...

    @abstractmethod
    def obtener_solicitud(self, solicitud_id: int) -> SolicitudEspecie | None: ...

    @abstractmethod
    def listar_solicitudes(self, usuario_id: int | None, estado: str | None) -> list[SolicitudEspecie]: ...

    @abstractmethod
    def resolver_solicitud(self, solicitud: SolicitudEspecie) -> bool:
        """Guarda la resolucion solo si la solicitud sigue PENDIENTE."""


# ---------------------------------------------------------------- usuarios y plantas

class RepositorioUsuariosPort(ABC):
    @abstractmethod
    def crear(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def obtener(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def por_nombre_o_email(self, identificador: str) -> Usuario | None: ...

    @abstractmethod
    def existe(self, nombre: str, email: str) -> bool: ...

    @abstractmethod
    def hay_admin(self) -> bool: ...

    @abstractmethod
    def listar(self) -> list[Usuario]: ...

    @abstractmethod
    def actualizar(self, usuario: Usuario) -> Usuario: ...


class RepositorioPlantasPort(ABC):
    @abstractmethod
    def crear(self, planta: Planta, propietario_id: int) -> Planta:
        """Crea la planta y el vinculo PROPIETARIO en una sola transaccion."""

    @abstractmethod
    def obtener(self, planta_id: int) -> Planta | None: ...

    @abstractmethod
    def actualizar(self, planta: Planta) -> Planta: ...

    @abstractmethod
    def eliminar(self, planta_id: int) -> None: ...

    @abstractmethod
    def vinculo(self, planta_id: int, usuario_id: int) -> TipoVinculo | None: ...

    @abstractmethod
    def quitar_vinculo(self, planta_id: int, usuario_id: int) -> None: ...

    @abstractmethod
    def listar_de_usuario(self, usuario_id: int) -> list[tuple[Planta, TipoVinculo]]: ...


# ---------------------------------------------------------------- dispositivos e invitaciones

class RepositorioDispositivosPort(ABC):
    @abstractmethod
    def registrar(self, dispositivo: Dispositivo) -> Dispositivo: ...

    @abstractmethod
    def guardar(self, dispositivo: Dispositivo) -> None: ...

    @abstractmethod
    def obtener(self, dispositivo_id: int) -> Dispositivo | None: ...

    @abstractmethod
    def por_mac(self, mac: str) -> Dispositivo | None: ...

    @abstractmethod
    def por_planta(self, planta_id: int) -> Dispositivo | None: ...

    @abstractmethod
    def vincular_si_emparejando(
        self, dispositivo_id: int, planta_id: int, token_hash: str, ahora: datetime
    ) -> bool:
        """Atomico (RA21): asigna solo si sigue EMPAREJANDO, la ventana no vencio y la planta esta libre."""

    @abstractmethod
    def revertir_vinculo(self, dispositivo_id: int) -> None:
        """Vuelve el dispositivo a SIN_VINCULAR y borra el hash del token (RA22)."""

    @abstractmethod
    def revocar(self, dispositivo_id: int) -> None:
        """Estado REVOCADO, sin planta y sin hash: el token deja de servir de inmediato (RA25)."""


class RepositorioInvitacionesPort(ABC):
    @abstractmethod
    def crear(self, invitacion: Invitacion) -> Invitacion: ...

    @abstractmethod
    def por_hash(self, token_hash: str) -> Invitacion | None: ...

    @abstractmethod
    def marcar_expirada(self, invitacion_id: int) -> None: ...

    @abstractmethod
    def consumir_y_vincular(self, invitacion_id: int, usuario_id: int, ahora: datetime) -> bool:
        """Atomico (RA21): consume la invitacion PENDIENTE y crea el vinculo CUIDADOR."""


class HistorialLecturasPort(ABC):
    @abstractmethod
    def guardar(self, medicion: Medicion) -> Medicion: ...

    @abstractmethod
    def ultima(self, planta_id: int) -> Medicion | None: ...

    @abstractmethod
    def listar(
        self, planta_id: int, desde: datetime | None, hasta: datetime | None, limite: int
    ) -> list[Medicion]: ...


# ---------------------------------------------------------------- seguridad

class HasherPasswordPort(ABC):
    @abstractmethod
    def hashear(self, password: str) -> str: ...

    @abstractmethod
    def verificar(self, password: str, password_hash: str) -> bool: ...


class EmisorJwtPort(ABC):
    @abstractmethod
    def emitir(self, identidad: Identidad) -> str: ...


class GeneradorTokenPort(ABC):
    """Token opaco aleatorio de al menos 256 bits; el servidor solo guarda su hash (RA11)."""

    @abstractmethod
    def generar(self) -> TokenOpaco: ...

    @abstractmethod
    def hashear(self, valor: str) -> str: ...

    @abstractmethod
    def coincide(self, valor: str, token_hash: str) -> bool: ...


# ---------------------------------------------------------------- notificaciones, tiempo y auditoria

class NotificadorDispositivoPort(ABC):
    @abstractmethod
    def entregar_token(self, mac: str, token: str) -> bool:
        """Entrega el token una sola vez por la conexion abierta. False si no se pudo confirmar."""


class NotificadorEstadoPort(ABC):
    @abstractmethod
    def publicar(self, medicion: Medicion) -> None:
        """Empuja el estado nuevo de la planta al front (RF19)."""


class RelojPort(ABC):
    @abstractmethod
    def ahora(self) -> datetime:
        """Hora actual con zona horaria (UTC)."""


class AuditoriaPort(ABC):
    @abstractmethod
    def registrar(self, entrada: EntradaAuditoria) -> None:
        """Nunca recibe ni guarda tokens (RA25)."""
