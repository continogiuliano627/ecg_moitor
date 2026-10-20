import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, tf2sos

from . import config


class ECGFilter:
    """Cascada SOS causal con estado persistente entre bloques. Sin dependencias de Qt."""

    def __init__(self, fs: float = config.FS,
                 highpass: bool = True, lowpass: bool = True, notch: bool = True):
        self._fs = fs
        self._sos = None
        self._zi = None
        self.configure(highpass, lowpass, notch)

    @property
    def sos(self):
        return self._sos

    def configure(self, highpass: bool, lowpass: bool, notch: bool) -> None:
        """Reconstruye la cascada y descarta el estado anterior."""
        nyq = self._fs / 2
        sections = []
        if highpass:
            sections.append(butter(config.HP_ORDER, config.HP_HZ, btype="highpass",
                                   fs=self._fs, output="sos"))
        if notch:
            if not 0 < config.MAINS_HZ < nyq:
                raise ValueError(f"MAINS_HZ={config.MAINS_HZ} fuera de (0, {nyq})")
            b, a = iirnotch(config.MAINS_HZ, config.NOTCH_Q, fs=self._fs)
            sections.append(tf2sos(b, a))
        if lowpass:
            sections.append(butter(config.LP_ORDER, config.LP_HZ, btype="lowpass",
                                   fs=self._fs, output="sos"))
        self._sos = np.vstack(sections) if sections else None
        self._zi = None

    def reset(self) -> None:
        """El próximo bloque reinicializa el estado con su primera muestra."""
        self._zi = None

    def process(self, block: np.ndarray) -> np.ndarray:
        x = np.asarray(block, dtype=np.float64)
        if self._sos is None or x.size == 0:
            return x.copy()
        if self._zi is None:
            # Estado estacionario para una entrada constante igual a x[0]:
            # evita el escalón de ~512 cuentas de offset visto por el pasa-alto.
            self._zi = sosfilt_zi(self._sos) * x[0]
        y, self._zi = sosfilt(self._sos, x, zi=self._zi)
        return y