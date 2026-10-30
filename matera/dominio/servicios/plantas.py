from matera.dominio.errores import DatosInvalidos, EspecieDesconocida, PermisoDenegado, RecursoNoEncontrado
from matera.dominio.modelo import (
    EntradaAuditoria,
    EventoAuditoria,
    Identidad,
    Planta,
    TipoVinculo,
    normalizar_especie,
)
from matera.dominio.politica_propiedad import PoliticaPropiedad
from matera.dominio.puertos.entrada import GestionarPlantasPort
from matera.dominio.puertos.salida import (
    AuditoriaPort,
    ConsultarRangosPort,
    RelojPort,
    RepositorioDispositivosPort,
    RepositorioPlantasPort,
)


class PlantasService(GestionarPlantasPort):
    def __init__(
        self,
        plantas: RepositorioPlantasPort,
        rangos: ConsultarRangosPort,
        dispositivos: RepositorioDispositivosPort,
        politica: PoliticaPropiedad,
        reloj: RelojPort,
        auditoria: AuditoriaPort,
    ):
        self._plantas = plantas
        self._rangos = rangos
        self._dispositivos = dispositivos
        self._politica = politica
        self._reloj = reloj
        self._auditoria = auditoria

    def crear(self, identidad: Identidad, apodo: str, especie: str) -> Planta:
        planta = Planta(
            id=None,
            apodo=self._validar_apodo(apodo),
            especie=self._validar_especie(especie),
            creada_en=self._reloj.ahora(),
        )
        return self._plantas.crear(planta, propietario_id=identidad.usuario_id)

    def editar(
        self, identidad: Identidad, planta_id: int, apodo: str | None, especie: str | None
    ) -> Planta:
        planta = self._politica.exigir_gestionar(identidad, planta_id)
        if apodo is not None:
            planta.apodo = self._validar_apodo(apodo)
        if especie is not None:
            planta.especie = self._validar_especie(especie)
        return self._plantas.actualizar(planta)

    def eliminar(self, identidad: Identidad, planta_id: int) -> None:
        self._politica.exigir_gestionar(identidad, planta_id)
        dispositivo = self._dispositivos.por_planta(planta_id)
        if dispositivo is not None:
            self._dispositivos.revocar(dispositivo.id)  # RA25: eliminar la planta revoca el token
            self._auditoria.registrar(EntradaAuditoria(
                evento=EventoAuditoria.DESVINCULACION,
                ocurrido_en=self._reloj.ahora(),
                usuario_id=identidad.usuario_id,
                dispositivo_id=dispositivo.id,
                planta_id=planta_id,
                detalle="planta eliminada",
            ))
        self._plantas.eliminar(planta_id)

    def desvincularse(self, identidad: Identidad, planta_id: int) -> None:
        planta = self._plantas.obtener(planta_id)
        vinculo = self._plantas.vinculo(planta_id, identidad.usuario_id)
        if planta is None or not planta.activa or vinculo is None:
            raise RecursoNoEncontrado("La planta no existe.", planta_id=planta_id)
        if vinculo == TipoVinculo.PROPIETARIO:
            raise PermisoDenegado("El propietario no puede desvincularse; debe eliminar la planta.")
        self._plantas.quitar_vinculo(planta_id, identidad.usuario_id)

    @staticmethod
    def _validar_apodo(apodo: str) -> str:
        apodo = (apodo or "").strip() if isinstance(apodo, str) else ""
        if not 1 <= len(apodo) <= 60:
            raise DatosInvalidos("El apodo debe tener entre 1 y 60 caracteres.", campo="apodo")
        return apodo

    def _validar_especie(self, especie: str) -> str:
        if not isinstance(especie, str) or not especie.strip():
            raise DatosInvalidos("Falta la especie.", campo="especie")
        nombre = normalizar_especie(especie)
        encontrada = self._rangos.obtener(nombre)
        if encontrada is None or not encontrada.activa:
            raise EspecieDesconocida("La especie no esta soportada.", especie=especie)
        return nombre
