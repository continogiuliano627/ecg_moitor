import time

import numpy as np

import serial

from .protocol import FrameParser
from . import config

# (centro en fase [0,1), ancho, amplitud relativa): ondas P, Q, R, S, T
_WAVES = (
    (0.18, 0.025, 0.12),
    (0.255, 0.008, -0.15),
    (0.28, 0.010, 1.00),
    (0.305, 0.010, -0.25),
    (0.50, 0.045, 0.30),
)


def _beat(phase: np.ndarray) -> np.ndarray:
    y = np.zeros_like(phase)
    for c, w, a in _WAVES:
        y += a * np.exp(-0.5 * ((phase - c) / w) ** 2)
    return y


class SimulatedECGSource:
    """Genera ECG sintético en cuentas ADC. Interfaz: start(), stop(), read()."""

    def __init__(self, fs: int = config.FS, heart_rate_bpm: float = 72.0,
                 mains_hz: float = 50.0):
        self._fs = fs
        self._hr = heart_rate_bpm
        self._mains = mains_hz
        self._rng = np.random.default_rng()
        self._t0 = 0.0
        self._n = 0

    def start(self) -> None:
        self._t0 = time.perf_counter()
        self._n = 0

    def stop(self) -> None:
        pass

    def read(self) -> np.ndarray:
        """Devuelve las muestras que corresponden al tiempo transcurrido."""
        total = int((time.perf_counter() - self._t0) * self._fs)
        n_new = total - self._n
        if n_new <= 0:
            return np.empty(0)
        t = (np.arange(self._n, total)) / self._fs
        self._n = total
        phase = (t * self._hr / 60.0) % 1.0
        sig = 512.0 + 300.0 * _beat(phase)
        sig += 20.0 * np.sin(2 * np.pi * 0.3 * t)        # deriva de línea base
        sig += 8.0 * np.sin(2 * np.pi * self._mains * t)  # interferencia de red
        sig += self._rng.normal(0.0, 3.0, n_new)          # ruido
        return np.clip(sig, 0, config.ADC_MAX)
    
class SerialSource:
    ##"""Lee tramas del Arduino. start() abre el puerto; se ejecuta en el hilo del worker."""

    def __init__(self, port: str, baud: int = config.BAUD):
           self._port = port
           self._baud = baud
           self._ser = None
           self._parser = FrameParser()
           self._t_ready = 0.0
           self._booted = False

    def start(self) -> None:
        self._parser.reset()
        self._ser = serial.Serial(self._port, self._baud, timeout=0, write_timeout=1)
        self._t_ready = time.perf_counter() + config.SERIAL_BOOT_S
        self._booted = False

    def stop(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def read(self) -> np.ndarray:
        if self._ser is None:
            return np.empty(0)
        n = self._ser.in_waiting
        data = self._ser.read(n) if n else b""
        if not self._booted:
            if time.perf_counter() < self._t_ready:
                return np.empty(0)          # descarta el arranque del bootloader
            self._ser.reset_input_buffer()
            self._parser.reset()
            self._booted = True
            return np.empty(0)
        return self._parser.feed(data)

    def info(self) -> dict:
        p = self._parser
        return {"frames": p.frames, "lost": p.lost, "bad": p.bad,
                "discarded": p.discarded, "lo_plus": p.lo_plus, "lo_minus": p.lo_minus}