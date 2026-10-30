"""Errores de negocio. Los adaptadores los traducen a codigos HTTP o mensajes WS."""


class ErrorDominio(Exception):
    codigo = "ERROR_DOMINIO"

    def __init__(self, mensaje: str, **detalle):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle


class DatosInvalidos(ErrorDominio):
    codigo = "DATOS_INVALIDOS"


class ParametroAusente(DatosInvalidos):
    codigo = "PARAMETRO_AUSENTE"


class ValorNoNumerico(DatosInvalidos):
    codigo = "VALOR_NO_NUMERICO"


class ValorFueraDeRangoFisico(DatosInvalidos):
    codigo = "VALOR_FUERA_DE_RANGO_FISICO"


class EspecieDesconocida(ErrorDominio):
    codigo = "ESPECIE_DESCONOCIDA"


class RecursoNoEncontrado(ErrorDominio):
    codigo = "RECURSO_NO_ENCONTRADO"


class PermisoDenegado(ErrorDominio):
    codigo = "PERMISO_DENEGADO"


class CredencialesInvalidas(ErrorDominio):
    codigo = "CREDENCIALES_INVALIDAS"


class Conflicto(ErrorDominio):
    codigo = "CONFLICTO"


class InvitacionNoDisponible(ErrorDominio):
    codigo = "INVITACION_NO_DISPONIBLE"


class EntregaTokenFallida(ErrorDominio):
    codigo = "ENTREGA_TOKEN_FALLIDA"
