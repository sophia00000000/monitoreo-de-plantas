from functools import wraps

import jwt
from flask import g

from matera.adaptadores.entrada.http.comun import NoAutenticado, token_bearer
from matera.dominio.modelo import Identidad, Rol


class JwtVerificador:
    """Verifica el JWT en el borde y entrega al caso de uso solo UsuarioId y rol (RA12).

    Usa la misma clave que JwtAdapter (el emisor). El dominio nunca ve el token ni las cabeceras.
    """

    ALGORITMO = "HS256"

    def __init__(self, secreto: str):
        self._secreto = secreto

    def verificar(self, token: str | None) -> Identidad:
        if not token:
            raise NoAutenticado("Se requiere iniciar sesion.")
        try:
            datos = jwt.decode(
                token,
                self._secreto,
                algorithms=[self.ALGORITMO],
                options={"require": ["exp", "sub", "rol"]},
            )
            return Identidad(usuario_id=int(datos["sub"]), rol=Rol(datos["rol"]))
        except (jwt.PyJWTError, ValueError, KeyError):
            raise NoAutenticado("La sesion no es valida o expiro.") from None

    def requerido(self, vista):
        """Decorador de Flask: deja la identidad en g.identidad o responde 401."""

        @wraps(vista)
        def envoltura(*args, **kwargs):
            g.identidad = self.verificar(token_bearer())
            return vista(*args, **kwargs)

        return envoltura
