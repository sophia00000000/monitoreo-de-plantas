from datetime import datetime, timedelta

from matera.dominio.errores import CredencialesInvalidas, DatosInvalidos
from matera.dominio.modelo import EstadoDispositivo, Lectura, Medicion, OrigenLectura
from matera.dominio.puertos.entrada import DiagnosticarPort, RegistrarLecturaPort
from matera.dominio.puertos.salida import (
    HistorialLecturasPort,
    NotificadorEstadoPort,
    RelojPort,
    RepositorioDispositivosPort,
    RepositorioPlantasPort,
)

TOLERANCIA_RELOJ_DISPOSITIVO = timedelta(minutes=5)


class RegistrarLecturaService(RegistrarLecturaPort):
    """Recibe la lectura de un dispositivo ya autenticado, la evalua, la guarda y la publica (RF12, RF19)."""

    def __init__(
        self,
        dispositivos: RepositorioDispositivosPort,
        plantas: RepositorioPlantasPort,
        evaluador: DiagnosticarPort,
        historial: HistorialLecturasPort,
        notificador: NotificadorEstadoPort,
        reloj: RelojPort,
    ):
        self._dispositivos = dispositivos
        self._plantas = plantas
        self._evaluador = evaluador
        self._historial = historial
        self._notificador = notificador
        self._reloj = reloj

    def registrar(
        self,
        dispositivo_id: int,
        lectura: Lectura,
        tomada_en: datetime | None,
        origen: OrigenLectura,
    ) -> Medicion:
        dispositivo = self._dispositivos.obtener(dispositivo_id)
        if (
            dispositivo is None
            or dispositivo.estado != EstadoDispositivo.VINCULADO
            or dispositivo.planta_id is None
        ):
            raise CredencialesInvalidas("El dispositivo no esta vinculado a ninguna planta.")
        planta = self._plantas.obtener(dispositivo.planta_id)
        if planta is None or not planta.activa:
            raise CredencialesInvalidas("El dispositivo no esta vinculado a ninguna planta.")

        ahora = self._reloj.ahora()
        tomada_en = tomada_en or ahora
        if tomada_en > ahora + TOLERANCIA_RELOJ_DISPOSITIVO:
            raise DatosInvalidos("La marca de tiempo de la lectura esta en el futuro.", campo="tomada_en")

        diagnostico = self._evaluador.diagnosticar(planta.especie, lectura)
        medicion = self._historial.guardar(Medicion(
            planta_id=planta.id,
            dispositivo_id=dispositivo.id,
            tomada_en=tomada_en,
            origen=origen,
            lectura=lectura,
            diagnostico=diagnostico,
            evaluado_en=ahora,
        ))
        try:
            self._notificador.publicar(medicion)
        except Exception:
            # La lectura ya quedo en el historial; el front la vera en su siguiente consulta.
            pass
        return medicion
