"""Piezas compartidas por los controladores HTTP: errores uniformes y conversion de la entrada (RA6)."""
from datetime import datetime, timezone
from math import isfinite

from flask import Flask, jsonify, request

from matera.dominio.errores import (
    Conflicto,
    CredencialesInvalidas,
    DatosInvalidos,
    EntregaTokenFallida,
    ErrorDominio,
    EspecieDesconocida,
    InvitacionNoDisponible,
    PermisoDenegado,
    RecursoNoEncontrado,
    ValorFueraDeRangoFisico,
    ValorNoNumerico,
)
from matera.dominio.modelo import PARAMETROS, Lectura, Rango

# Orden importa: de lo mas especifico a lo mas general.
_ESTADOS_HTTP: list[tuple[type[ErrorDominio], int]] = [
    (ValorFueraDeRangoFisico, 422),
    (DatosInvalidos, 400),
    (EspecieDesconocida, 404),
    (RecursoNoEncontrado, 404),
    (CredencialesInvalidas, 401),
    (PermisoDenegado, 403),
    (Conflicto, 409),
    (InvitacionNoDisponible, 410),
    (EntregaTokenFallida, 502),
]


class NoAutenticado(Exception):
    """No hay identidad verificada (JWT ausente, invalido o vencido): 401 (RA9)."""


def error_json(codigo: str, mensaje: str, status: int, detalle: dict | None = None):
    return jsonify({"error": codigo, "mensaje": mensaje, "detalle": detalle or {}}), status


def estado_http(error: ErrorDominio) -> int:
    return next((status for tipo, status in _ESTADOS_HTTP if isinstance(error, tipo)), 400)


def registrar_manejadores_error(app: Flask) -> None:
    @app.errorhandler(ErrorDominio)
    def _dominio(error: ErrorDominio):
        return error_json(error.codigo, error.mensaje, estado_http(error), error.detalle)

    @app.errorhandler(NoAutenticado)
    def _no_autenticado(error):
        return error_json("NO_AUTENTICADO", str(error) or "Se requiere iniciar sesion.", 401)

    @app.errorhandler(404)
    def _no_encontrado(error):
        return error_json("RECURSO_NO_ENCONTRADO", "El recurso solicitado no existe.", 404)

    @app.errorhandler(405)
    def _metodo(error):
        return error_json("METODO_NO_PERMITIDO", "El metodo HTTP no esta permitido para este recurso.", 405)

    @app.errorhandler(429)
    def _limite(error):
        return error_json("DEMASIADOS_INTENTOS", "Demasiados intentos. Espere un momento.", 429)

    @app.errorhandler(500)
    def _interno(error):
        return error_json("ERROR_INTERNO", "Ocurrio un error interno en el servidor.", 500)


# ---------------------------------------------------------------- lectura del cuerpo

def cuerpo_json() -> dict:
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise DatosInvalidos("El cuerpo debe ser un objeto JSON valido.")
    return datos


def texto(datos: dict, campo: str, requerido: bool = True) -> str | None:
    valor = datos.get(campo)
    if valor is None and not requerido:
        return None
    if not isinstance(valor, str) or (requerido and not valor.strip()):
        raise DatosInvalidos(f"Falta el campo: {campo}.", campo=campo)
    return valor


def numero(valor, campo: str) -> float:
    if isinstance(valor, bool):
        raise ValorNoNumerico(f"El campo {campo} debe ser numerico.", campo=campo)
    try:
        resultado = float(valor)
    except (TypeError, ValueError):
        raise ValorNoNumerico(f"El campo {campo} debe ser numerico.", campo=campo) from None
    if not isfinite(resultado):
        raise ValorNoNumerico(f"El campo {campo} debe ser un numero finito.", campo=campo)
    return resultado


def leer_lectura(datos: dict) -> Lectura:
    """Convierte los valores presentes a numero. Los ausentes los detecta el dominio (RF6)."""
    valores = {
        codigo: numero(datos[codigo], codigo)
        for codigo in PARAMETROS
        if datos.get(codigo) not in (None, "")
    }
    return Lectura(valores=valores)


def leer_rangos(datos: dict) -> dict[str, Rango]:
    rangos = datos.get("rangos")
    if not isinstance(rangos, dict):
        raise DatosInvalidos("Falta el objeto 'rangos'.", campo="rangos")
    resultado = {}
    for codigo, rango in rangos.items():
        if not isinstance(rango, dict):
            raise DatosInvalidos(f"Rango invalido para {codigo}.", campo=codigo)
        resultado[codigo] = Rango(
            numero(rango.get("minimo"), f"{codigo}.minimo"),
            numero(rango.get("maximo"), f"{codigo}.maximo"),
        )
    return resultado


def leer_fecha(valor, campo: str) -> datetime | None:
    if valor in (None, ""):
        return None
    if not isinstance(valor, str):
        raise DatosInvalidos(f"El campo {campo} debe ser una fecha ISO-8601.", campo=campo)
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        raise DatosInvalidos(f"El campo {campo} debe ser una fecha ISO-8601.", campo=campo) from None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def entero(valor, campo: str, por_defecto: int) -> int:
    if valor in (None, ""):
        return por_defecto
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise DatosInvalidos(f"El campo {campo} debe ser entero.", campo=campo) from None


def token_bearer() -> str | None:
    cabecera = request.headers.get("Authorization", "")
    tipo, _, token = cabecera.partition(" ")
    return token.strip() if tipo.lower() == "bearer" and token.strip() else None
