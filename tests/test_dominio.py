import unittest

from modelos import CondicionesAmbientales
from dominio.puertos import FuenteConfiguracionPlantas
from repositorios.planta_repository import PlantaRepository
from servicios.criterios import CriterioFactory, CriterioRango
from servicios.evaluador import Evaluador


class AdaptadorEnMemoria(FuenteConfiguracionPlantas):
    """Doble de prueba: entrega configuracion sin leer archivos reales."""

    def cargar_configuracion_criterios(self) -> list[dict]:
        return [
            {
                "nombre": "Sansevieria de prueba",
                "especie": "sansevieria",
                "criterios": [
                    {"nombre": "humedad", "minimo": 30, "maximo": 60, "unidad": "%"},
                    {"nombre": "iluminacion", "minimo": 100, "maximo": 800, "unidad": "lux"},
                    {"nombre": "temperatura", "minimo": 18, "maximo": 35, "unidad": "C"},
                ],
            }
        ]


def crear_evaluador() -> Evaluador:
    repository = PlantaRepository(AdaptadorEnMemoria())
    return Evaluador(repository, CriterioFactory())


class ReglasDeDominioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluador = crear_evaluador()

    def test_valor_inferior_al_rango_es_bajo(self):
        criterio = CriterioRango(type("Configuracion", (), {"minimo": 30, "maximo": 60})())

        self.assertEqual(criterio.evaluar(29.9), "BAJO")

    def test_valor_superior_al_rango_es_alto(self):
        criterio = CriterioRango(type("Configuracion", (), {"minimo": 30, "maximo": 60})())

        self.assertEqual(criterio.evaluar(60.1), "ALTO")

    def test_limites_incluidos_son_optimos(self):
        criterio = CriterioRango(type("Configuracion", (), {"minimo": 30, "maximo": 60})())

        self.assertEqual(criterio.evaluar(30), "OPTIMO")
        self.assertEqual(criterio.evaluar(60), "OPTIMO")

    def test_todos_los_parametros_optimos_dan_indice_saludable(self):
        resultado = self.evaluador.evaluar_planta(
            "sansevieria",
            CondicionesAmbientales({"humedad": 40, "iluminacion": 300, "temperatura": 22}),
        )

        self.assertEqual(resultado.indice_vitalidad, "SALUDABLE")
        self.assertEqual(resultado.recomendaciones, [])
        self.assertTrue(all(item["estado"] == "OPTIMO" for item in resultado.criterios.values()))

    def test_un_parametro_fuera_de_rango_dan_indice_en_riesgo_y_recomendacion(self):
        resultado = self.evaluador.evaluar_planta(
            "sansevieria",
            CondicionesAmbientales({"humedad": 20, "iluminacion": 300, "temperatura": 22}),
        )

        self.assertEqual(resultado.indice_vitalidad, "EN_RIESGO")
        self.assertEqual(resultado.criterios["humedad"]["estado"], "BAJO")
        self.assertEqual(len(resultado.recomendaciones), 1)

    def test_dos_parametros_fuera_de_rango_dan_indice_critico(self):
        resultado = self.evaluador.evaluar_planta(
            "sansevieria",
            CondicionesAmbientales({"humedad": 20, "iluminacion": 900, "temperatura": 22}),
        )

        self.assertEqual(resultado.indice_vitalidad, "CRITICO")
        self.assertEqual(resultado.criterios["iluminacion"]["estado"], "ALTO")
        self.assertEqual(len(resultado.recomendaciones), 2)

    def test_condicion_ausente_es_rechazada_por_el_dominio(self):
        with self.assertRaisesRegex(ValueError, "Falta la condicion: temperatura"):
            self.evaluador.evaluar_planta(
                "sansevieria",
                CondicionesAmbientales({"humedad": 40, "iluminacion": 300}),
            )

    def test_especie_desconocida_es_rechazada_por_el_caso_de_uso(self):
        with self.assertRaisesRegex(ValueError, "Especie no soportada"):
            self.evaluador.evaluar_planta(
                "especie_inexistente",
                CondicionesAmbientales({"humedad": 40, "iluminacion": 300, "temperatura": 22}),
            )


if __name__ == "__main__":
    unittest.main()
