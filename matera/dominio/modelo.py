"""Entidades y objetos de valor del dominio.

Este modulo no importa nada de Flask, SQL, CSV, JSON ni JWT (RA4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Mapping

from matera.dominio.errores import DatosInvalidos


# ---------------------------------------------------------------- enumeraciones

class Rol(StrEnum):
    """Rol de cuenta: viaja en el JWT."""
    USUARIO = "USUARIO"
    ADMIN = "ADMIN"


class TipoVinculo(StrEnum):
    """Vinculo con la planta: lo decide el dominio (PoliticaPropiedad)."""
    PROPIETARIO = "PROPIETARIO"
    CUIDADOR = "CUIDADOR"


class EstadoParametro(StrEnum):
    BAJO = "BAJO"
    OPTIMO = "OPTIMO"
    ALTO = "ALTO"


class EstadoGlobal(StrEnum):
    SALUDABLE = "SALUDABLE"
    EN_RIESGO = "EN_RIESGO"
    CRITICO = "CRITICO"


class EstadoDispositivo(StrEnum):
    SIN_VINCULAR = "SIN_VINCULAR"
    EMPAREJANDO = "EMPAREJANDO"
    VINCULADO = "VINCULADO"
    REVOCADO = "REVOCADO"


class EstadoInvitacion(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONSUMIDA = "CONSUMIDA"
    EXPIRADA = "EXPIRADA"
    REVOCADA = "REVOCADA"


class EstadoSolicitud(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"


class EventoAuditoria(StrEnum):
    EMPAREJAMIENTO = "EMPAREJAMIENTO"
    VINCULACION = "VINCULACION"
    VINCULACION_REVERTIDA = "VINCULACION_REVERTIDA"
    DESVINCULACION = "DESVINCULACION"
    CANJE = "CANJE"
    INTENTO_FALLIDO = "INTENTO_FALLIDO"
    ACCESO_ADMIN = "ACCESO_ADMIN"


class OrigenLectura(StrEnum):
    HTTP = "HTTP"
    WS = "WS"


# ---------------------------------------------------------------- constantes de negocio

VENTANA_EMPAREJAMIENTO = timedelta(minutes=10)  # RA22


@dataclass(frozen=True)
class Parametro:
    """Magnitud que mide la matera, con su rango fisicamente posible (RF6)."""
    codigo: str
    unidad: str
    min_fisico: float
    max_fisico: float
    etiqueta: str


PARAMETROS: dict[str, Parametro] = {
    "humedad": Parametro("humedad", "%", 0, 100, "La humedad"),
    "luz": Parametro("luz", "lux", 0, 200_000, "La luz"),
    "temperatura": Parametro("temperatura", "C", -50, 60, "La temperatura"),
}


# ---------------------------------------------------------------- utilidades de valor

_PATRON_MAC = re.compile(r"^[0-9A-F]{2}([:-]?[0-9A-F]{2}){5}$")


def normalizar_especie(nombre: str) -> str:
    """Clave canonica de una especie: minusculas, sin espacios repetidos."""
    return "_".join(nombre.strip().lower().replace("-", " ").split())


def normalizar_mac(mac: str) -> str:
    """Devuelve la MAC en formato AA:BB:CC:DD:EE:FF. La MAC identifica, no autentica (RA11)."""
    if not isinstance(mac, str) or not _PATRON_MAC.match(mac.strip().upper()):
        raise DatosInvalidos("La MAC no tiene un formato valido.", campo="mac")
    hexa = re.sub(r"[^0-9A-F]", "", mac.upper())
    return ":".join(hexa[i:i + 2] for i in range(0, 12, 2))


# ---------------------------------------------------------------- catalogo

@dataclass(frozen=True)
class Rango:
    minimo: float
    maximo: float

    def __post_init__(self):
        if not self.minimo < self.maximo:
            raise DatosInvalidos("El minimo debe ser menor que el maximo.")


@dataclass(frozen=True)
class Especie:
    nombre: str
    nombre_cientifico: str
    fuente: str
    rangos: Mapping[str, Rango]
    activa: bool = True
    id: int | None = None


# ---------------------------------------------------------------- diagnostico

@dataclass(frozen=True)
class Lectura:
    """Valores medidos ya convertidos a numero por el adaptador de entrada (RA6)."""
    valores: Mapping[str, float]


@dataclass(frozen=True)
class EvaluacionParametro:
    parametro: str
    valor: float
    unidad: str
    minimo: float
    maximo: float
    estado: EstadoParametro
    recomendacion: str | None


@dataclass(frozen=True)
class Diagnostico:
    especie: str
    estado_global: EstadoGlobal
    parametros: tuple[EvaluacionParametro, ...]

    @property
    def recomendaciones(self) -> list[str]:
        return [p.recomendacion for p in self.parametros if p.recomendacion]


# ---------------------------------------------------------------- identidades y cuentas

@dataclass(frozen=True)
class Identidad:
    """Lo unico que el dominio sabe de quien llama: ya verificado en el borde (RA12)."""
    usuario_id: int
    rol: Rol

    @property
    def es_admin(self) -> bool:
        return self.rol == Rol.ADMIN


@dataclass
class Usuario:
    id: int | None
    nombre: str
    email: str
    password_hash: str
    rol: Rol
    activo: bool
    creado_en: datetime


@dataclass(frozen=True)
class Sesion:
    token: str
    usuario: Usuario


# ---------------------------------------------------------------- plantas

@dataclass
class Planta:
    id: int | None
    apodo: str
    especie: str
    creada_en: datetime
    activa: bool = True


@dataclass
class Dispositivo:
    id: int | None
    mac: str
    estado: EstadoDispositivo
    planta_id: int | None
    token_hash: str | None
    ventana_expira_en: datetime | None
    registrado_en: datetime


@dataclass
class Medicion:
    planta_id: int
    dispositivo_id: int | None
    tomada_en: datetime
    origen: OrigenLectura
    lectura: Lectura
    diagnostico: Diagnostico
    evaluado_en: datetime
    id: int | None = None


@dataclass(frozen=True)
class PlantaDetalle:
    """Vista de lectura de una planta para quien la consulta (RF13)."""
    planta: Planta
    vinculo: TipoVinculo | None
    dispositivo: Dispositivo | None
    ultima_medicion: Medicion | None


# ---------------------------------------------------------------- invitaciones

@dataclass
class Invitacion:
    id: int | None
    planta_id: int
    creada_por: int
    token_hash: str
    estado: EstadoInvitacion
    expira_en: datetime
    creada_en: datetime
    canjeada_por: int | None = None


@dataclass(frozen=True)
class InvitacionEmitida:
    """El token en claro solo existe aqui, una vez, para devolverlo al propietario."""
    token: str
    planta_id: int
    expira_en: datetime


@dataclass(frozen=True)
class TokenOpaco:
    valor: str
    hash: str


# ---------------------------------------------------------------- solicitudes de especie

@dataclass
class SolicitudEspecie:
    id: int | None
    usuario_id: int
    nombre_propuesto: str
    justificacion: str
    estado: EstadoSolicitud
    creada_en: datetime
    resuelta_por: int | None = None
    resuelta_en: datetime | None = None
    especie_id: int | None = None


# ---------------------------------------------------------------- auditoria

@dataclass(frozen=True)
class EntradaAuditoria:
    evento: EventoAuditoria
    ocurrido_en: datetime
    usuario_id: int | None = None
    dispositivo_id: int | None = None
    planta_id: int | None = None
    detalle: str | None = None
    extra: dict = field(default_factory=dict)
