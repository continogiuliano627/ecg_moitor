import os
import tempfile
import wave

import numpy as np

try:
    import winsound
except ImportError:          # no es Windows
    winsound = None


def make_wav(path: str, freq: float = 1000.0, dur_ms: float = 40.0,
             ramp_ms: float = 5.0, rate: int = 44100, amp: float = 0.5) -> None:
    """Tono senoidal con rampa de entrada y salida (evita el clic de los extremos)."""
    n = int(rate * dur_ms / 1000.0)
    t = np.arange(n) / rate
    y = np.sin(2 * np.pi * freq * t)
    r = max(1, int(rate * ramp_ms / 1000.0))
    env = np.ones(n)
    env[:r] = np.linspace(0.0, 1.0, r)
    env[-r:] = np.linspace(1.0, 0.0, r)
    pcm = (amp * 32767.0 * y * env).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


class HeartBeeper:
    """Pitido breve y no bloqueante. winsound no admite SND_MEMORY con SND_ASYNC,
    por eso el WAV se escribe una vez en un archivo temporal."""

    def __init__(self, freq: float = 1000.0, dur_ms: float = 40.0):
        self._path = os.path.join(tempfile.gettempdir(), "ecg_app_beep.wav")
        make_wav(self._path, freq=freq, dur_ms=dur_ms)

    @property
    def available(self) -> bool:
        return winsound is not None

    def play(self) -> None:
        if winsound is None:
            return
        try:
            winsound.PlaySound(self._path,
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass                 # un fallo de audio no debe afectar a la adquisición

    def stop(self) -> None:
        if winsound is None:
            return
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass