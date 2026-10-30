import re

from matera.dominio.errores import Conflicto, CredencialesInvalidas, DatosInvalidos
from matera.dominio.modelo import (
    EntradaAuditoria,
    EventoAuditoria,
    Identidad,
    Rol,
    Sesion,
    Usuario,
)
from matera.dominio.puertos.entrada import AutenticarUsuarioPort
from matera.dominio.puertos.salida import (
    AuditoriaPort,
    EmisorJwtPort,
    HasherPasswordPort,
    RelojPort,
    RepositorioUsuariosPort,
)

_PATRON_NOMBRE = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
_PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LONGITUD_MINIMA_PASSWORD = 8


class AutenticacionService(AutenticarUsuarioPort):
    """Valida credenciales y pide la firma del JWT a EmisorJwtPort (RF8, RF9, RA10)."""

    def __init__(
        self,
        usuarios: RepositorioUsuariosPort,
        hasher: HasherPasswordPort,
        emisor: EmisorJwtPort,
        reloj: RelojPort,
        auditoria: AuditoriaPort,
    ):
        self._usuarios = usuarios
        self._hasher = hasher
        self._emisor = emisor
        self._reloj = reloj
        self._auditoria = auditoria
        self._hash_senuelo: str | None = None

    def registrar(self, nombre: str, email: str, password: str, rol: Rol = Rol.USUARIO) -> Usuario:
        nombre = (nombre or "").strip()
        email = (email or "").strip().lower()
        if not _PATRON_NOMBRE.match(nombre):
            raise DatosInvalidos(
                "El nombre de usuario debe tener entre 3 y 40 caracteres (letras, numeros, _ . -).",
                campo="nombre",
            )
        if not _PATRON_EMAIL.match(email):
            raise DatosInvalidos("El correo no es valido.", campo="email")
        if not isinstance(password, str) or len(password) < LONGITUD_MINIMA_PASSWORD:
            raise DatosInvalidos(
                f"La contrasena debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.",
                campo="password",
            )
        if self._usuarios.existe(nombre, email):
            raise Conflicto("No fue posible registrar la cuenta con esos datos.")
        return self._usuarios.crear(Usuario(
            id=None,
            nombre=nombre,
            email=email,
            password_hash=self._hasher.hashear(password),
            rol=rol,
            activo=True,
            creado_en=self._reloj.ahora(),
        ))

    def iniciar_sesion(self, identificador: str, password: str) -> Sesion:
        usuario = self._usuarios.por_nombre_o_email((identificador or "").strip())
        if usuario is None:
            # Se verifica contra un hash senuelo para que el tiempo de respuesta no revele si existe (RA24).
            self._hasher.verificar(password or "", self._senuelo())
            valido = False
        else:
            valido = self._hasher.verificar(password or "", usuario.password_hash) and usuario.activo
        if not valido:
            self._auditoria.registrar(EntradaAuditoria(
                evento=EventoAuditoria.INTENTO_FALLIDO,
                ocurrido_en=self._reloj.ahora(),
                usuario_id=usuario.id if usuario else None,
                detalle="login",
            ))
            raise CredencialesInvalidas("Usuario o contrasena incorrectos.")
        token = self._emisor.emitir(Identidad(usuario_id=usuario.id, rol=usuario.rol))
        return Sesion(token=token, usuario=usuario)

    def asegurar_admin(self, nombre: str, email: str, password: str) -> None:
        """Crea el primer admin si todavia no existe ninguno (lo invoca la composicion)."""
        if not self._usuarios.hay_admin():
            self.registrar(nombre, email, password, rol=Rol.ADMIN)

    def _senuelo(self) -> str:
        if self._hash_senuelo is None:
            self._hash_senuelo = self._hasher.hashear("contrasena-senuelo")
        return self._hash_senuelo
