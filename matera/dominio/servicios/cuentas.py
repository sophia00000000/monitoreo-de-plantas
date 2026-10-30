from matera.dominio.errores import Conflicto, RecursoNoEncontrado
from matera.dominio.modelo import Identidad, Rol, Usuario
from matera.dominio.politica_propiedad import exigir_admin
from matera.dominio.puertos.entrada import GestionarCuentasPort
from matera.dominio.puertos.salida import RepositorioUsuariosPort


class CuentasService(GestionarCuentasPort):
    def __init__(self, usuarios: RepositorioUsuariosPort):
        self._usuarios = usuarios

    def listar(self, identidad: Identidad) -> list[Usuario]:
        exigir_admin(identidad)
        return self._usuarios.listar()

    def actualizar(
        self, identidad: Identidad, usuario_id: int, activo: bool | None, rol: Rol | None
    ) -> Usuario:
        exigir_admin(identidad)
        usuario = self._usuarios.obtener(usuario_id)
        if usuario is None:
            raise RecursoNoEncontrado("La cuenta no existe.", usuario_id=usuario_id)
        if usuario_id == identidad.usuario_id and (activo is False or rol == Rol.USUARIO):
            raise Conflicto("Un administrador no puede desactivarse ni quitarse el rol a si mismo.")
        if activo is not None:
            usuario.activo = activo
        if rol is not None:
            usuario.rol = rol
        return self._usuarios.actualizar(usuario)
