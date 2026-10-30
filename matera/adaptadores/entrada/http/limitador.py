import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, request


class LimitadorIntentos:
    """Limite de intentos por IP y operacion, en ventana deslizante (RA24). Responde 429 uniforme."""

    def __init__(self, maximo: int = 10, ventana_segundos: float = 60):
        self._maximo = maximo
        self._ventana = ventana_segundos
        self._intentos: dict[str, deque] = defaultdict(deque)
        self._candado = threading.Lock()

    def permitir(self, clave: str) -> bool:
        ahora = time.monotonic()
        with self._candado:
            intentos = self._intentos[clave]
            while intentos and ahora - intentos[0] > self._ventana:
                intentos.popleft()
            if len(intentos) >= self._maximo:
                return False
            intentos.append(ahora)
            return True

    def limitar(self, operacion: str):
        def decorador(vista):
            @wraps(vista)
            def envoltura(*args, **kwargs):
                if not self.permitir(f"{operacion}:{request.remote_addr}"):
                    abort(429)
                return vista(*args, **kwargs)

            return envoltura

        return decorador
