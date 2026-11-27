from dataclasses import replace
from datetime import datetime, timedelta

from matera.dominio.errores import CredencialesInvalidas, DatosInvalidos
from matera.dominio.modelo import EstadoDispositivo, Lectura, Medicion, OrigenLectura
from matera.dominio.puertos.entrada import DiagnosticarPort, RegistrarLecturaPort
from matera.dominio.puertos.salida import (
    HistorialLecturasPort,
    NotificadorDispositivoPort,
    NotificadorEstadoPort,
    ReglasAnimoPort,
    RelojPort,
    RepositorioDispositivosPort,
    RepositorioPlantasPort,
)
from matera.dominio.servicios.animo import EvaluadorAnimo

TOLERANCIA_RELOJ_DISPOSITIVO = timedelta(minutes=5)


class RegistrarLecturaService(RegistrarLecturaPort):
    """Recibe la lectura de un dispositivo ya autenticado, la evalua, la guarda y la publica (RF12, RF19).

    Solo coordina (SRP): el diagnostico lo decide DiagnosticarPort, el animo EvaluadorAnimo, y los
    puertos de salida traducen a SQL o WebSocket (DIP).
    """

    def __init__(
        self,
        dispositivos: RepositorioDispositivosPort,
        plantas: RepositorioPlantasPort,
        evaluador: DiagnosticarPort,
        historial: HistorialLecturasPort,
        notificador: NotificadorEstadoPort,
        reloj: RelojPort,
        reglas_animo: ReglasAnimoPort,
        evaluador_animo: EvaluadorAnimo,
        notificador_dispositivo: NotificadorDispositivoPort,
    ):
        self._dispositivos = dispositivos
        self._plantas = plantas
        self._evaluador = evaluador
        self._historial = historial
        self._notificador = notificador
        self._reloj = reloj
        self._reglas_animo = reglas_animo
        self._evaluador_animo = evaluador_animo
        self._notificador_dispositivo = notificador_dispositivo

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
        animo = self._evaluador_animo.evaluar(diagnostico, self._reglas_animo.listar())
        medicion = self._historial.guardar(Medicion(
            planta_id=planta.id,
            dispositivo_id=dispositivo.id,
            tomada_en=tomada_en,
            origen=origen,
            lectura=lectura,
            diagnostico=replace(diagnostico, animo=animo),
            evaluado_en=ahora,
        ))
        try:
            self._notificador.publicar(medicion)
        except Exception:
            # La lectura ya quedo en el historial; el front la vera en su siguiente consulta.
            pass
        # Si la matera no esta conectada devuelve False: la medicion ya esta guardada y la pantalla
        # sigue con su animo local (animoSimulado) hasta la siguiente lectura.
        self._notificador_dispositivo.notificar_animo(dispositivo.mac, animo)
        return medicion
