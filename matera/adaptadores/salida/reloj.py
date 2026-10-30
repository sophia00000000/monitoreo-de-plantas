from datetime import datetime, timezone

from matera.dominio.puertos.salida import RelojPort


class RelojSistema(RelojPort):
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)
