import numpy as np


class RingBuffer:
    """Búfer circular de tamaño fijo. Escribir y leer solo desde el hilo de la GUI."""

    def __init__(self, size: int):
        self._size = size
        self._data = np.zeros(size, dtype=np.float64)
        self._idx = 0      # próxima posición de escritura
        self._count = 0    # muestras válidas (<= size)

    def append(self, block: np.ndarray) -> None:
        n = len(block)
        if n == 0:
            return
        if n >= self._size:
            self._data[:] = block[-self._size:]
            self._idx = 0
            self._count = self._size
            return
        end = self._idx + n
        if end <= self._size:
            self._data[self._idx:end] = block
        else:
            first = self._size - self._idx
            self._data[self._idx:] = block[:first]
            self._data[:n - first] = block[first:]
        self._idx = end % self._size
        self._count = min(self._count + n, self._size)

    def snapshot(self) -> np.ndarray:
        """Copia ordenada de la más antigua a la más reciente."""
        if self._count < self._size:
            return self._data[:self._count].copy()
        return np.concatenate((self._data[self._idx:], self._data[:self._idx]))

    def clear(self) -> None:
        self._idx = 0
        self._count = 0