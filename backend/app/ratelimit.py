"""Limitador de uso por ventana deslizante, en memoria.

Cuenta las llamadas de cada clave (un cliente, una dirección IP) en el último minuto. El conteo
vive en el proceso: con varios procesos de la API, cada uno cuenta por su cuenta, así que el límite
real es como máximo `límite × procesos`. Para un límite exacto entre procesos haría falta un
almacén compartido (por ejemplo Redis).
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, limit: Callable[[], int], window_seconds: float = 60.0):
        # `limit` es una función para leer el valor de la configuración en cada llamada.
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> float | None:
        """Registra una llamada. Devuelve None si se permite, o los segundos de espera si no."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit():
                return max(self._window - (now - hits[0]), 1.0)
            hits.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
