"""Configuracion leida de variables de entorno (RA23). Ningun secreto vive en el codigo."""
import os
import secrets
import warnings
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _entorno(nombre: str, por_defecto: str | None = None) -> str | None:
    valor = os.environ.get(nombre)
    return valor if valor not in (None, "") else por_defecto


@dataclass
class Configuracion:
    # csv | json | sqlite: tabla de referencia de especies (RA15)
    fuente_especies: str = "csv"
    ruta_csv: Path = RAIZ / "configuracion" / "especies.csv"
    ruta_json: Path = RAIZ / "configuracion" / "especies.json"
    ruta_bd: Path = RAIZ / "datos" / "matera.db"
    jwt_secreto: str = ""
    jwt_minutos: int = 60
    invitacion_minutos: int = 60 * 24
    espera_token_dispositivo: float = 10.0
    limite_intentos: int = 10
    ventana_limite_segundos: int = 60
    origenes_cors: list[str] = field(default_factory=lambda: ["http://127.0.0.1:5500", "http://localhost:5500"])
    admin_usuario: str | None = None
    admin_email: str | None = None
    admin_password: str | None = None
    rondas_bcrypt: int = 12

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        secreto = _entorno("MATERA_JWT_SECRETO")
        if secreto is None:
            secreto = secrets.token_urlsafe(48)
            warnings.warn(
                "MATERA_JWT_SECRETO no esta definida: se genero una clave temporal. "
                "Las sesiones se invalidan al reiniciar el servidor.",
                stacklevel=2,
            )
        origenes = _entorno("MATERA_CORS_ORIGENES")
        config = cls(
            fuente_especies=(_entorno("MATERA_FUENTE_ESPECIES", "csv")).lower(),
            jwt_secreto=secreto,
            jwt_minutos=int(_entorno("MATERA_JWT_MINUTOS", "60")),
            invitacion_minutos=int(_entorno("MATERA_INVITACION_MINUTOS", str(60 * 24))),
            admin_usuario=_entorno("MATERA_ADMIN_USUARIO"),
            admin_email=_entorno("MATERA_ADMIN_EMAIL"),
            admin_password=_entorno("MATERA_ADMIN_PASSWORD"),
        )
        if _entorno("MATERA_BD"):
            config.ruta_bd = Path(_entorno("MATERA_BD"))
        if _entorno("MATERA_CSV"):
            config.ruta_csv = Path(_entorno("MATERA_CSV"))
        if origenes:
            config.origenes_cors = [o.strip() for o in origenes.split(",") if o.strip()]
        return config
