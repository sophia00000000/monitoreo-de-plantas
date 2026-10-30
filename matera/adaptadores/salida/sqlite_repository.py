"""Repositorios SQLite de usuarios, plantas, dispositivos e invitaciones."""
from matera.adaptadores.salida.base_datos import BaseDatosSqlite, a_fecha, a_texto
from matera.dominio.modelo import (
    Dispositivo,
    EstadoDispositivo,
    EstadoInvitacion,
    Invitacion,
    Planta,
    Rol,
    TipoVinculo,
    Usuario,
)
from matera.dominio.puertos.salida import (
    RepositorioDispositivosPort,
    RepositorioInvitacionesPort,
    RepositorioPlantasPort,
    RepositorioUsuariosPort,
)


class SqliteUsuarios(RepositorioUsuariosPort):
    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def crear(self, usuario: Usuario) -> Usuario:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """INSERT INTO usuario (email, nombre, password_hash, rol, activo, creado_en)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (usuario.email, usuario.nombre, usuario.password_hash, usuario.rol.value,
                 int(usuario.activo), a_texto(usuario.creado_en)),
            )
            usuario.id = cursor.lastrowid
        return usuario

    def obtener(self, usuario_id: int) -> Usuario | None:
        return self._uno("SELECT * FROM usuario WHERE id = ?", (usuario_id,))

    def por_nombre_o_email(self, identificador: str) -> Usuario | None:
        return self._uno(
            "SELECT * FROM usuario WHERE nombre = ? OR email = ?",
            (identificador, identificador.lower()),
        )

    def existe(self, nombre: str, email: str) -> bool:
        return self._uno("SELECT * FROM usuario WHERE nombre = ? OR email = ?", (nombre, email)) is not None

    def hay_admin(self) -> bool:
        return self._uno("SELECT * FROM usuario WHERE rol = 'ADMIN' LIMIT 1", ()) is not None

    def listar(self) -> list[Usuario]:
        with self._bd.lectura() as conexion:
            return [self._usuario(f) for f in conexion.execute("SELECT * FROM usuario ORDER BY id")]

    def actualizar(self, usuario: Usuario) -> Usuario:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                "UPDATE usuario SET rol = ?, activo = ? WHERE id = ?",
                (usuario.rol.value, int(usuario.activo), usuario.id),
            )
        return usuario

    def _uno(self, consulta: str, argumentos: tuple) -> Usuario | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute(consulta, argumentos).fetchone()
            return self._usuario(fila) if fila else None

    @staticmethod
    def _usuario(fila) -> Usuario:
        return Usuario(
            id=fila["id"],
            nombre=fila["nombre"],
            email=fila["email"],
            password_hash=fila["password_hash"],
            rol=Rol(fila["rol"]),
            activo=bool(fila["activo"]),
            creado_en=a_fecha(fila["creado_en"]),
        )


class SqlitePlantas(RepositorioPlantasPort):
    _SELECT = """SELECT p.id, p.apodo, p.creada_en, p.activa, e.nombre AS especie
                 FROM planta p JOIN especie e ON e.id = p.especie_id"""

    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def crear(self, planta: Planta, propietario_id: int) -> Planta:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                "INSERT INTO planta (especie_id, apodo, creada_en, activa) VALUES (?, ?, ?, 1)",
                (self._especie_id(conexion, planta.especie), planta.apodo, a_texto(planta.creada_en)),
            )
            planta.id = cursor.lastrowid
            conexion.execute(
                "INSERT INTO vinculo_planta (usuario_id, planta_id, tipo, creado_en) VALUES (?, ?, 'PROPIETARIO', ?)",
                (propietario_id, planta.id, a_texto(planta.creada_en)),
            )
        return planta

    def obtener(self, planta_id: int) -> Planta | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute(self._SELECT + " WHERE p.id = ?", (planta_id,)).fetchone()
            return self._planta(fila) if fila else None

    def actualizar(self, planta: Planta) -> Planta:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                "UPDATE planta SET apodo = ?, especie_id = ? WHERE id = ?",
                (planta.apodo, self._especie_id(conexion, planta.especie), planta.id),
            )
        return planta

    def eliminar(self, planta_id: int) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute("UPDATE planta SET activa = 0 WHERE id = ?", (planta_id,))
            conexion.execute(
                "UPDATE invitacion SET estado = 'REVOCADA' WHERE planta_id = ? AND estado = 'PENDIENTE'",
                (planta_id,),
            )

    def vinculo(self, planta_id: int, usuario_id: int) -> TipoVinculo | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute(
                "SELECT tipo FROM vinculo_planta WHERE planta_id = ? AND usuario_id = ?",
                (planta_id, usuario_id),
            ).fetchone()
            return TipoVinculo(fila["tipo"]) if fila else None

    def quitar_vinculo(self, planta_id: int, usuario_id: int) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                "DELETE FROM vinculo_planta WHERE planta_id = ? AND usuario_id = ? AND tipo = 'CUIDADOR'",
                (planta_id, usuario_id),
            )

    def listar_de_usuario(self, usuario_id: int) -> list[tuple[Planta, TipoVinculo]]:
        with self._bd.lectura() as conexion:
            filas = conexion.execute(
                self._SELECT.replace("SELECT", "SELECT v.tipo,", 1)
                + " JOIN vinculo_planta v ON v.planta_id = p.id WHERE v.usuario_id = ? ORDER BY p.id",
                (usuario_id,),
            ).fetchall()
            return [(self._planta(f), TipoVinculo(f["tipo"])) for f in filas]

    @staticmethod
    def _especie_id(conexion, nombre: str) -> int:
        fila = conexion.execute("SELECT id FROM especie WHERE nombre = ?", (nombre,)).fetchone()
        if fila is None:
            # La especie viene validada por el dominio contra la tabla de referencia configurada
            # (CSV/JSON/BD); si esa tabla no es la BD, se registra aqui para mantener la FK.
            fila = [conexion.execute(
                "INSERT INTO especie (nombre, fuente, activa) VALUES (?, 'tabla de referencia externa', 1)",
                (nombre,),
            ).lastrowid]
        return fila[0]

    @staticmethod
    def _planta(fila) -> Planta:
        return Planta(
            id=fila["id"],
            apodo=fila["apodo"],
            especie=fila["especie"],
            creada_en=a_fecha(fila["creada_en"]),
            activa=bool(fila["activa"]),
        )


class SqliteDispositivos(RepositorioDispositivosPort):
    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def registrar(self, dispositivo: Dispositivo) -> Dispositivo:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """INSERT INTO dispositivo (planta_id, mac, estado, token_hash, ventana_expira_en, registrado_en)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dispositivo.planta_id, dispositivo.mac, dispositivo.estado.value, dispositivo.token_hash,
                 a_texto(dispositivo.ventana_expira_en), a_texto(dispositivo.registrado_en)),
            )
            dispositivo.id = cursor.lastrowid
        return dispositivo

    def guardar(self, dispositivo: Dispositivo) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                """UPDATE dispositivo SET planta_id = ?, estado = ?, token_hash = ?, ventana_expira_en = ?
                   WHERE id = ?""",
                (dispositivo.planta_id, dispositivo.estado.value, dispositivo.token_hash,
                 a_texto(dispositivo.ventana_expira_en), dispositivo.id),
            )

    def obtener(self, dispositivo_id: int) -> Dispositivo | None:
        return self._uno("SELECT * FROM dispositivo WHERE id = ?", (dispositivo_id,))

    def por_mac(self, mac: str) -> Dispositivo | None:
        return self._uno("SELECT * FROM dispositivo WHERE mac = ?", (mac,))

    def por_planta(self, planta_id: int) -> Dispositivo | None:
        return self._uno("SELECT * FROM dispositivo WHERE planta_id = ? AND estado = 'VINCULADO'", (planta_id,))

    def vincular_si_emparejando(self, dispositivo_id: int, planta_id: int, token_hash: str, ahora) -> bool:
        with self._bd.transaccion() as conexion:
            ocupada = conexion.execute(
                "SELECT 1 FROM dispositivo WHERE planta_id = ? AND estado = 'VINCULADO'", (planta_id,)
            ).fetchone()
            if ocupada:
                return False
            cursor = conexion.execute(
                """UPDATE dispositivo SET estado = 'VINCULADO', planta_id = ?, token_hash = ?,
                       ventana_expira_en = NULL
                   WHERE id = ? AND estado = 'EMPAREJANDO' AND ventana_expira_en > ?""",
                (planta_id, token_hash, dispositivo_id, a_texto(ahora)),
            )
            return cursor.rowcount == 1

    def revertir_vinculo(self, dispositivo_id: int) -> None:
        self._cambiar_estado(dispositivo_id, EstadoDispositivo.SIN_VINCULAR)

    def revocar(self, dispositivo_id: int) -> None:
        self._cambiar_estado(dispositivo_id, EstadoDispositivo.REVOCADO)

    def _cambiar_estado(self, dispositivo_id: int, estado: EstadoDispositivo) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                """UPDATE dispositivo SET estado = ?, planta_id = NULL, token_hash = NULL, ventana_expira_en = NULL
                   WHERE id = ?""",
                (estado.value, dispositivo_id),
            )

    def _uno(self, consulta: str, argumentos: tuple) -> Dispositivo | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute(consulta, argumentos).fetchone()
        if fila is None:
            return None
        return Dispositivo(
            id=fila["id"],
            mac=fila["mac"],
            estado=EstadoDispositivo(fila["estado"]),
            planta_id=fila["planta_id"],
            token_hash=fila["token_hash"],
            ventana_expira_en=a_fecha(fila["ventana_expira_en"]),
            registrado_en=a_fecha(fila["registrado_en"]),
        )


class SqliteInvitaciones(RepositorioInvitacionesPort):
    def __init__(self, bd: BaseDatosSqlite):
        self._bd = bd

    def crear(self, invitacion: Invitacion) -> Invitacion:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """INSERT INTO invitacion (planta_id, creada_por, token_hash, estado, expira_en, creada_en)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invitacion.planta_id, invitacion.creada_por, invitacion.token_hash,
                 invitacion.estado.value, a_texto(invitacion.expira_en), a_texto(invitacion.creada_en)),
            )
            invitacion.id = cursor.lastrowid
        return invitacion

    def por_hash(self, token_hash: str) -> Invitacion | None:
        with self._bd.lectura() as conexion:
            fila = conexion.execute("SELECT * FROM invitacion WHERE token_hash = ?", (token_hash,)).fetchone()
        if fila is None:
            return None
        return Invitacion(
            id=fila["id"],
            planta_id=fila["planta_id"],
            creada_por=fila["creada_por"],
            token_hash=fila["token_hash"],
            estado=EstadoInvitacion(fila["estado"]),
            expira_en=a_fecha(fila["expira_en"]),
            creada_en=a_fecha(fila["creada_en"]),
            canjeada_por=fila["canjeada_por"],
        )

    def marcar_expirada(self, invitacion_id: int) -> None:
        with self._bd.transaccion() as conexion:
            conexion.execute(
                "UPDATE invitacion SET estado = 'EXPIRADA' WHERE id = ? AND estado = 'PENDIENTE'",
                (invitacion_id,),
            )

    def consumir_y_vincular(self, invitacion_id: int, usuario_id: int, ahora) -> bool:
        with self._bd.transaccion() as conexion:
            cursor = conexion.execute(
                """UPDATE invitacion SET estado = 'CONSUMIDA', canjeada_por = ?
                   WHERE id = ? AND estado = 'PENDIENTE' AND expira_en > ?""",
                (usuario_id, invitacion_id, a_texto(ahora)),
            )
            if cursor.rowcount != 1:
                return False
            planta_id = conexion.execute(
                "SELECT planta_id FROM invitacion WHERE id = ?", (invitacion_id,)
            ).fetchone()[0]
            conexion.execute(
                """INSERT INTO vinculo_planta (usuario_id, planta_id, tipo, creado_en) VALUES (?, ?, 'CUIDADOR', ?)
                   ON CONFLICT (usuario_id, planta_id) DO NOTHING""",
                (usuario_id, planta_id, a_texto(ahora)),
            )
            return True
