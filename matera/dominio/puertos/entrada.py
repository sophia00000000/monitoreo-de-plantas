"""Puertos de entrada: casos de uso con nombre de negocio.

No saben si los invoca HTTP, WebSocket o una prueba. Reciben identidades ya verificadas (RA12).
"""
from abc import ABC, abstractmethod
from datetime import datetime

from matera.dominio.modelo import (
    Diagnostico,
    Dispositivo,
    Especie,
    Identidad,
    InvitacionEmitida,
    Lectura,
    Medicion,
    OrigenLectura,
    Planta,
    PlantaDetalle,
    Rol,
    Sesion,
    SolicitudEspecie,
    Usuario,
)


class DiagnosticarPort(ABC):
    """Diagnostico ad hoc sin persistir (RF1-RF4, RF6, RF7)."""

    @abstractmethod
    def diagnosticar(self, especie: str, lectura: Lectura) -> Diagnostico: ...


class ConsultarCatalogoPort(ABC):
    """Lista de especies soportadas con sus rangos (RF5)."""

    @abstractmethod
    def listar_especies(self) -> list[Especie]: ...


class AutenticarUsuarioPort(ABC):
    """Registro e inicio de sesion (RF8, RF9)."""

    @abstractmethod
    def registrar(self, nombre: str, email: str, password: str) -> Usuario: ...

    @abstractmethod
    def iniciar_sesion(self, identificador: str, password: str) -> Sesion: ...


class GestionarPlantasPort(ABC):
    """Crear, editar, eliminar plantas y desvincularse como cuidador (RF10)."""

    @abstractmethod
    def crear(self, identidad: Identidad, apodo: str, especie: str) -> Planta: ...

    @abstractmethod
    def editar(
        self, identidad: Identidad, planta_id: int, apodo: str | None, especie: str | None
    ) -> Planta: ...

    @abstractmethod
    def eliminar(self, identidad: Identidad, planta_id: int) -> None: ...

    @abstractmethod
    def desvincularse(self, identidad: Identidad, planta_id: int) -> None: ...


class ConsultarPlantaPort(ABC):
    """Lectura mas reciente, estado actual e historial filtrable (RF13, RF14)."""

    @abstractmethod
    def listar(self, identidad: Identidad) -> list[PlantaDetalle]: ...

    @abstractmethod
    def detalle(self, identidad: Identidad, planta_id: int) -> PlantaDetalle: ...

    @abstractmethod
    def historial(
        self,
        identidad: Identidad,
        planta_id: int,
        desde: datetime | None,
        hasta: datetime | None,
        limite: int,
    ) -> list[Medicion]: ...


class VincularDispositivoPort(ABC):
    """Vincular y desvincular un dispositivo de una planta (RF11, RF21)."""

    @abstractmethod
    def vincular(self, identidad: Identidad, planta_id: int, mac: str) -> Dispositivo: ...

    @abstractmethod
    def desvincular(self, identidad: Identidad, planta_id: int) -> None: ...


class EmparejarDispositivoPort(ABC):
    """El dispositivo anuncia su MAC y abre la ventana de 10 minutos (RF20, RA22)."""

    @abstractmethod
    def anunciar(self, mac: str) -> datetime:
        """Devuelve cuando vence la ventana de emparejamiento."""

    @abstractmethod
    def cancelar(self, mac: str) -> None:
        """La conexion se cerro sin vincular: el dispositivo vuelve a su estado inicial."""


class AutenticarDispositivoPort(ABC):
    """Compara el token con su hash y la MAC; devuelve el DispositivoId (RA11, RA12)."""

    @abstractmethod
    def autenticar(self, mac: str, token: str) -> int: ...


class RegistrarLecturaPort(ABC):
    """Evalua, guarda y publica la lectura de un dispositivo ya autenticado (RF12, RF19)."""

    @abstractmethod
    def registrar(
        self,
        dispositivo_id: int,
        lectura: Lectura,
        tomada_en: datetime | None,
        origen: OrigenLectura,
    ) -> Medicion: ...


class CompartirPlantaPort(ABC):
    """Invitacion de un solo uso para co-cuidar una planta (RF15, RA20, RA21)."""

    @abstractmethod
    def generar_invitacion(self, identidad: Identidad, planta_id: int) -> InvitacionEmitida: ...

    @abstractmethod
    def canjear(self, identidad: Identidad, token: str) -> Planta: ...


class GestionarCuentasPort(ABC):
    """El admin consulta, desactiva y cambia el rol de las cuentas (RF18)."""

    @abstractmethod
    def listar(self, identidad: Identidad) -> list[Usuario]: ...

    @abstractmethod
    def actualizar(
        self, identidad: Identidad, usuario_id: int, activo: bool | None, rol: Rol | None
    ) -> Usuario: ...


class GestionarEspeciesPort(ABC):
    """Solicitudes de especie y gestion del catalogo (RF16, RF17)."""

    @abstractmethod
    def solicitar(self, identidad: Identidad, nombre: str, justificacion: str) -> SolicitudEspecie: ...

    @abstractmethod
    def listar_solicitudes(self, identidad: Identidad, estado: str | None) -> list[SolicitudEspecie]: ...

    @abstractmethod
    def aprobar(self, identidad: Identidad, solicitud_id: int, especie: Especie) -> SolicitudEspecie: ...

    @abstractmethod
    def rechazar(self, identidad: Identidad, solicitud_id: int) -> SolicitudEspecie: ...

    @abstractmethod
    def guardar_especie(self, identidad: Identidad, especie: Especie) -> Especie: ...

    @abstractmethod
    def desactivar_especie(self, identidad: Identidad, nombre: str) -> None: ...
