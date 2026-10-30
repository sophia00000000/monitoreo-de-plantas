"""Adaptadores de seguridad: hash de contrasenas, firma de JWT y tokens opacos."""
import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

import bcrypt
import jwt

from matera.dominio.modelo import Identidad, TokenOpaco
from matera.dominio.puertos.salida import (
    EmisorJwtPort,
    GeneradorTokenPort,
    HasherPasswordPort,
    RelojPort,
)


class BcryptHasher(HasherPasswordPort):
    """Hash adaptativo (RA10). Se pre-hashea con SHA-256 porque bcrypt solo usa 72 bytes."""

    def __init__(self, rondas: int = 12):
        self._rondas = rondas

    def hashear(self, password: str) -> str:
        return bcrypt.hashpw(self._prehash(password), bcrypt.gensalt(self._rondas)).decode("ascii")

    def verificar(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(self._prehash(password), password_hash.encode("ascii"))
        except ValueError:
            return False

    @staticmethod
    def _prehash(password: str) -> bytes:
        return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


class JwtAdapter(EmisorJwtPort):
    """Firma el JWT con identidad, rol y expiracion. La misma clave la usa JwtVerificador."""

    ALGORITMO = "HS256"

    def __init__(self, secreto: str, reloj: RelojPort, duracion: timedelta = timedelta(hours=1)):
        self._secreto = secreto
        self._reloj = reloj
        self._duracion = duracion

    def emitir(self, identidad: Identidad) -> str:
        ahora = self._reloj.ahora()
        return jwt.encode(
            {
                "sub": str(identidad.usuario_id),
                "rol": identidad.rol.value,
                "iat": ahora,
                "exp": ahora + self._duracion,
            },
            self._secreto,
            algorithm=self.ALGORITMO,
        )


class TokenOpacoGenerator(GeneradorTokenPort):
    """Token aleatorio de 256 bits (modulo secrets); se guarda solo su SHA-256 (RA11)."""

    BYTES = 32

    def generar(self) -> TokenOpaco:
        valor = secrets.token_urlsafe(self.BYTES)
        return TokenOpaco(valor=valor, hash=self.hashear(valor))

    def hashear(self, valor: str) -> str:
        return hashlib.sha256(valor.encode("utf-8")).hexdigest()

    def coincide(self, valor: str, token_hash: str) -> bool:
        return hmac.compare_digest(self.hashear(valor), token_hash)
