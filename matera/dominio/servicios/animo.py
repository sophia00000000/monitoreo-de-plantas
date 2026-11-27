"""Regla de negocio del animo de la mascota (RF12, RF19).

Usa los parametros ya evaluados con los rangos de la especie, no umbrales fijos: la misma lectura
puede dejar sedienta a una especie y feliz a otra.
"""
from typing import Iterable

from matera.dominio.modelo import Animo, Diagnostico, ReglaAnimo


class EvaluadorAnimo:
    """Funcion pura (SRP): solo decide el animo. No consulta la BD ni notifica a nadie."""

    def evaluar(self, diagnostico: Diagnostico, reglas: Iterable[ReglaAnimo]) -> Animo:
        """Entre las reglas cuyo (parametro, estado) aparece en el diagnostico gana la de menor prioridad.

        Si ninguna coincide la planta esta FELIZ.
        """
        estados = {(p.parametro, p.estado) for p in diagnostico.parametros}
        coincidentes = [r for r in reglas if (r.parametro, r.estado) in estados]
        if not coincidentes:
            return Animo.FELIZ
        return min(coincidentes, key=lambda r: r.prioridad).animo
