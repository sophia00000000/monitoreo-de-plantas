"""Dobles de prueba de los puertos de salida (AdapterEnMemoria, RelojFijo, AuditoriaEnMemoria...).

Permiten probar el dominio sin servidor, sin archivos y sin base de datos (RA19).
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from matera.dominio.modelo import (
    Dispositivo,
    EntradaAuditoria,
    Especie,
    EstadoDispositivo,
    EstadoInvitacion,
    EstadoSolicitud,
    Identidad,
    Invitacion,
    Medicion,
    Planta,
    Rango,
    Rol,
    SolicitudEspecie,
    TipoVinculo,
    TokenOpaco,
    Usuario,
)
from matera.dominio.puertos.salida import (
    AuditoriaPort,
    ConsultarRangosPort,
    EmisorJwtPort,
    GeneradorTokenPort,
    HasherPasswordPort,
    HistorialLecturasPort,
    NotificadorDispositivoPort,
    NotificadorEstadoPort,
    RelojPort,
    RepositorioDispositivosPort,
    RepositorioEspeciesPort,
    RepositorioInvitacionesPort,
    RepositorioPlantasPort,
    RepositorioUsuariosPort,
)

SANSEVIERIA = Especie(
    nombre="sansevieria",
    nombre_cientifico="Sansevieria de prueba",
    fuente="prueba",
    rangos={
        "humedad": Rango(30, 60),
        "luz": Rango(100, 800),
        "temperatura": Rango(18, 35),
    },
)


class RelojFijo(RelojPort):
    def __init__(self, inicio: datetime | None = None):
        self.actual = inicio or datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    def ahora(self) -> datetime:
        return self.actual

    def avanzar(self, **delta) -> None:
        self.actual += timedelta(**delta)


class AdapterEnMemoria(ConsultarRangosPort, RepositorioEspeciesPort):
    """Tabla de referencia y solicitudes en memoria."""

    def __init__(self, especies: list[Especie] | None = None):
        self._especies = {e.nombre: e for e in (especies if especies is not None else [SANSEVIERIA])}
        self._solicitudes: dict[int, SolicitudEspecie] = {}

    def obtener(self, nombre: str) -> Especie | None:
        return self._especies.get(nombre)

    def listar(self) -> list[Especie]:
        return [e for e in self._especies.values() if e.activa]

    def existe(self, nombre: str) -> bool:
        especie = self._especies.get(nombre)
        return especie is not None and especie.activa

    def guardar_especie(self, especie: Especie) -> Especie:
        guardada = replace(especie, id=len(self._especies) + 1)
        self._especies[especie.nombre] = guardada
        return guardada

    def desactivar_especie(self, nombre: str) -> bool:
        if nombre not in self._especies:
            return False
        self._especies[nombre] = replace(self._especies[nombre], activa=False)
        return True

    def crear_solicitud(self, solicitud: SolicitudEspecie) -> SolicitudEspecie:
        solicitud.id = len(self._solicitudes) + 1
        self._solicitudes[solicitud.id] = solicitud
        return solicitud

    def obtener_solicitud(self, solicitud_id: int) -> SolicitudEspecie | None:
        solicitud = self._solicitudes.get(solicitud_id)
        return replace(solicitud) if solicitud else None

    def listar_solicitudes(self, usuario_id, estado) -> list[SolicitudEspecie]:
        return [
            s for s in self._solicitudes.values()
            if (usuario_id is None or s.usuario_id == usuario_id) and (estado is None or s.estado == estado)
        ]

    def resolver_solicitud(self, solicitud: SolicitudEspecie) -> bool:
        if self._solicitudes[solicitud.id].estado != EstadoSolicitud.PENDIENTE:
            return False
        self._solicitudes[solicitud.id] = replace(solicitud)
        return True


class UsuariosEnMemoria(RepositorioUsuariosPort):
    def __init__(self):
        self.usuarios: dict[int, Usuario] = {}

    def crear(self, usuario: Usuario) -> Usuario:
        usuario.id = len(self.usuarios) + 1
        self.usuarios[usuario.id] = replace(usuario)
        return usuario

    def obtener(self, usuario_id: int) -> Usuario | None:
        usuario = self.usuarios.get(usuario_id)
        return replace(usuario) if usuario else None

    def por_nombre_o_email(self, identificador: str) -> Usuario | None:
        return next(
            (replace(u) for u in self.usuarios.values() if identificador in (u.nombre, u.email)), None
        )

    def existe(self, nombre: str, email: str) -> bool:
        return any(u.nombre == nombre or u.email == email for u in self.usuarios.values())

    def hay_admin(self) -> bool:
        return any(u.rol == Rol.ADMIN for u in self.usuarios.values())

    def listar(self) -> list[Usuario]:
        return [replace(u) for u in self.usuarios.values()]

    def actualizar(self, usuario: Usuario) -> Usuario:
        self.usuarios[usuario.id] = replace(usuario)
        return usuario


class PlantasEnMemoria(RepositorioPlantasPort):
    def __init__(self):
        self.plantas: dict[int, Planta] = {}
        self.vinculos: dict[tuple[int, int], TipoVinculo] = {}

    def crear(self, planta: Planta, propietario_id: int) -> Planta:
        planta.id = len(self.plantas) + 1
        self.plantas[planta.id] = replace(planta)
        self.vinculos[(planta.id, propietario_id)] = TipoVinculo.PROPIETARIO
        return planta

    def obtener(self, planta_id: int) -> Planta | None:
        planta = self.plantas.get(planta_id)
        return replace(planta) if planta else None

    def actualizar(self, planta: Planta) -> Planta:
        self.plantas[planta.id] = replace(planta)
        return planta

    def eliminar(self, planta_id: int) -> None:
        self.plantas[planta_id].activa = False

    def vinculo(self, planta_id: int, usuario_id: int) -> TipoVinculo | None:
        return self.vinculos.get((planta_id, usuario_id))

    def agregar_vinculo(self, planta_id: int, usuario_id: int, tipo: TipoVinculo) -> None:
        self.vinculos[(planta_id, usuario_id)] = tipo

    def quitar_vinculo(self, planta_id: int, usuario_id: int) -> None:
        if self.vinculos.get((planta_id, usuario_id)) == TipoVinculo.CUIDADOR:
            del self.vinculos[(planta_id, usuario_id)]

    def listar_de_usuario(self, usuario_id: int) -> list[tuple[Planta, TipoVinculo]]:
        return [
            (replace(self.plantas[p]), tipo) for (p, u), tipo in self.vinculos.items() if u == usuario_id
        ]


class DispositivosEnMemoria(RepositorioDispositivosPort):
    def __init__(self):
        self.dispositivos: dict[int, Dispositivo] = {}

    def registrar(self, dispositivo: Dispositivo) -> Dispositivo:
        dispositivo.id = len(self.dispositivos) + 1
        self.dispositivos[dispositivo.id] = replace(dispositivo)
        return dispositivo

    def guardar(self, dispositivo: Dispositivo) -> None:
        self.dispositivos[dispositivo.id] = replace(dispositivo)

    def obtener(self, dispositivo_id: int) -> Dispositivo | None:
        d = self.dispositivos.get(dispositivo_id)
        return replace(d) if d else None

    def por_mac(self, mac: str) -> Dispositivo | None:
        return next((replace(d) for d in self.dispositivos.values() if d.mac == mac), None)

    def por_planta(self, planta_id: int) -> Dispositivo | None:
        return next(
            (replace(d) for d in self.dispositivos.values()
             if d.planta_id == planta_id and d.estado == EstadoDispositivo.VINCULADO),
            None,
        )

    def vincular_si_emparejando(self, dispositivo_id, planta_id, token_hash, ahora) -> bool:
        d = self.dispositivos[dispositivo_id]
        if self.por_planta(planta_id) or d.estado != EstadoDispositivo.EMPAREJANDO or d.ventana_expira_en <= ahora:
            return False
        d.estado, d.planta_id, d.token_hash, d.ventana_expira_en = (
            EstadoDispositivo.VINCULADO, planta_id, token_hash, None
        )
        return True

    def revertir_vinculo(self, dispositivo_id: int) -> None:
        self._limpiar(dispositivo_id, EstadoDispositivo.SIN_VINCULAR)

    def revocar(self, dispositivo_id: int) -> None:
        self._limpiar(dispositivo_id, EstadoDispositivo.REVOCADO)

    def _limpiar(self, dispositivo_id: int, estado: EstadoDispositivo) -> None:
        d = self.dispositivos[dispositivo_id]
        d.estado, d.planta_id, d.token_hash, d.ventana_expira_en = estado, None, None, None


class InvitacionesEnMemoria(RepositorioInvitacionesPort):
    def __init__(self, plantas: PlantasEnMemoria):
        self._plantas = plantas
        self.invitaciones: dict[int, Invitacion] = {}

    def crear(self, invitacion: Invitacion) -> Invitacion:
        invitacion.id = len(self.invitaciones) + 1
        self.invitaciones[invitacion.id] = replace(invitacion)
        return invitacion

    def por_hash(self, token_hash: str) -> Invitacion | None:
        return next((replace(i) for i in self.invitaciones.values() if i.token_hash == token_hash), None)

    def marcar_expirada(self, invitacion_id: int) -> None:
        self.invitaciones[invitacion_id].estado = EstadoInvitacion.EXPIRADA

    def consumir_y_vincular(self, invitacion_id: int, usuario_id: int, ahora) -> bool:
        inv = self.invitaciones[invitacion_id]
        if inv.estado != EstadoInvitacion.PENDIENTE or inv.expira_en <= ahora:
            return False
        inv.estado, inv.canjeada_por = EstadoInvitacion.CONSUMIDA, usuario_id
        self._plantas.agregar_vinculo(inv.planta_id, usuario_id, TipoVinculo.CUIDADOR)
        return True


class HistorialEnMemoria(HistorialLecturasPort):
    def __init__(self):
        self.mediciones: list[Medicion] = []

    def guardar(self, medicion: Medicion) -> Medicion:
        medicion.id = len(self.mediciones) + 1
        self.mediciones.append(medicion)
        return medicion

    def ultima(self, planta_id: int) -> Medicion | None:
        resultado = self.listar(planta_id, None, None, 1)
        return resultado[0] if resultado else None

    def listar(self, planta_id, desde, hasta, limite) -> list[Medicion]:
        filtradas = [
            m for m in self.mediciones
            if m.planta_id == planta_id
            and (desde is None or m.tomada_en >= desde)
            and (hasta is None or m.tomada_en <= hasta)
        ]
        return sorted(filtradas, key=lambda m: (m.tomada_en, m.id), reverse=True)[:limite]


class HasherFalso(HasherPasswordPort):
    def hashear(self, password: str) -> str:
        return f"hash::{password}"

    def verificar(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hash::{password}"


class EmisorJwtFalso(EmisorJwtPort):
    def emitir(self, identidad: Identidad) -> str:
        return f"jwt-{identidad.usuario_id}-{identidad.rol.value}"


class GeneradorTokenFalso(GeneradorTokenPort):
    def __init__(self):
        self._contador = 0

    def generar(self) -> TokenOpaco:
        self._contador += 1
        valor = f"token-{self._contador}"
        return TokenOpaco(valor=valor, hash=self.hashear(valor))

    def hashear(self, valor: str) -> str:
        return f"h({valor})"

    def coincide(self, valor: str, token_hash: str) -> bool:
        return self.hashear(valor) == token_hash


class NotificadorDispositivoFalso(NotificadorDispositivoPort):
    def __init__(self, exito: bool = True):
        self.exito = exito
        self.entregados: list[tuple[str, str]] = []

    def entregar_token(self, mac: str, token: str) -> bool:
        if self.exito:
            self.entregados.append((mac, token))
        return self.exito


class NotificadorEstadoFalso(NotificadorEstadoPort):
    def __init__(self):
        self.publicadas: list[Medicion] = []

    def publicar(self, medicion: Medicion) -> None:
        self.publicadas.append(medicion)


class AuditoriaEnMemoria(AuditoriaPort):
    def __init__(self):
        self.entradas: list[EntradaAuditoria] = []

    def registrar(self, entrada: EntradaAuditoria) -> None:
        self.entradas.append(entrada)

    def eventos(self) -> list[str]:
        return [e.evento.value for e in self.entradas]
