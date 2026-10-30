"""Verifica RA4/RA12: ningun modulo del dominio importa framework, persistencia, HTTP, JSON ni JWT."""
import ast
import unittest
from pathlib import Path

DOMINIO = Path(__file__).resolve().parent.parent / "matera" / "dominio"
PROHIBIDOS = {
    "flask", "flask_cors", "flask_sock", "werkzeug", "simple_websocket",
    "jwt", "bcrypt", "sqlite3", "csv", "json", "http", "urllib", "requests",
    "hashlib", "hmac", "secrets", "matera.adaptadores", "matera.app", "matera.config",
}


def _imports(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(nodo.module)
    return nombres


class AislamientoDelDominioTest(unittest.TestCase):
    def test_el_dominio_no_importa_infraestructura(self):
        violaciones = []
        for archivo in DOMINIO.rglob("*.py"):
            for modulo in _imports(archivo):
                if any(modulo == p or modulo.startswith(p + ".") for p in PROHIBIDOS):
                    violaciones.append(f"{archivo.relative_to(DOMINIO)} importa {modulo}")
        self.assertEqual(violaciones, [])


if __name__ == "__main__":
    unittest.main()
