from collections import deque

import numpy as np
from scipy.signal import butter, lfilter, sosfilt, sosfilt_zi

from . import config


class RPeakDetector:
    """Detector de QRS en flujo (tipo Pan-Tompkins simplificado). Causal, sin Qt.

    Cadena: pasa-banda 5-15 Hz -> derivada -> cuadrado -> media móvil 100 ms
    -> máximos locales con umbral adaptativo y periodo refractario.
    Los índices son absolutos: contador de muestras desde reset().
    """

    def __init__(self, fs: float = config.FS):
        self._fs = fs
        self._sos = butter(2, [config.QRS_BAND_LO, config.QRS_BAND_HI],
                           btype="bandpass", fs=fs, output="sos")
        self._ma_n = max(1, int(round(config.QRS_MA_S * fs)))
        self._ma_b = np.ones(self._ma_n) / self._ma_n
        self._refractory = int(config.QRS_REFRACTORY_S * fs)
        self._search = int(config.QRS_SEARCH_S * fs)
        self._rescue = int(config.QRS_RESCUE_S * fs)
        self._hist_len = int(2.0 * fs)
        self.peaks = deque(maxlen=64)   # índices absolutos de los picos R recientes
        self.n = 0                      # muestras procesadas
        self.reset()

    def reset(self) -> None:
        """Reinicio total: contador de muestras, picos y estado."""
        self.n = 0
        self.peaks.clear()
        self.resync()

    def resync(self) -> None:
        """Descarta estado interno (tras pérdida de muestras). Conserva n y los picos ya marcados."""
        self._zi_bp = None
        self._zi_ma = np.zeros(self._ma_n - 1)
        self._prev_bp = 0.0
        self._hist = np.empty(0)
        self._hist_start = self.n
        self._m1 = 0.0
        self._m2 = 0.0
        self._learn_left = int(config.QRS_LEARN_S * self._fs)
        self._learn_max = 0.0
        self._spki = 0.0
        self._npki = 0.0
        self._ref = self.n
        self._last_r = None
        self._rr = deque(maxlen=config.RR_HISTORY)

    @property
    def bpm(self):
        """Mediana de los últimos RR válidos, en lpm; None si hay menos de 2 intervalos o poca calidad."""
        if len(self._rr) < 2 or self.snr < config.QRS_MIN_SNR:
            return None
        return 60.0 * self._fs / float(np.median(self._rr))

    @property
    def snr(self) -> float:
        """Cociente SPKI/NPKI: nivel de picos QRS sobre nivel de picos de ruido. Indicador de calidad."""
        if self._learn_left > 0 or self._npki <= 0.0:
            return 0.0
        return self._spki / self._npki

    @property
    def learning(self) -> bool:
        return self._learn_left > 0

    def process(self, block: np.ndarray) -> list:
        """Procesa un bloque contiguo. Devuelve los índices absolutos de picos R nuevos."""
        x = np.asarray(block, dtype=np.float64)
        if x.size == 0:
            return []
        if self._zi_bp is None:
            self._zi_bp = sosfilt_zi(self._sos) * x[0]   # sin escalón por el offset de ADC
        bp, self._zi_bp = sosfilt(self._sos, x, zi=self._zi_bp)
        d = np.diff(np.concatenate(([self._prev_bp], bp)))
        self._prev_bp = bp[-1]
        m, self._zi_ma = lfilter(self._ma_b, [1.0], d * d, zi=self._zi_ma)

        self._hist = np.concatenate((self._hist, x))
        if len(self._hist) > self._hist_len:
            drop = len(self._hist) - self._hist_len
            self._hist = self._hist[drop:]
            self._hist_start += drop

        found = []
        base = self.n
        for k in range(len(m)):
            cur = m[k]
            idx = base + k
            if self._learn_left > 0:
                self._learn_max = max(self._learn_max, cur)
                self._learn_left -= 1
                if self._learn_left == 0:
                    self._spki = self._learn_max
                    self._npki = 0.1 * self._learn_max
                    self._ref = idx
            else:
                if self._m1 > self._m2 and self._m1 >= cur:
                    self._candidate(idx - 1, self._m1, found)
                if idx - self._ref > self._rescue:
                    # Sin detecciones durante QRS_RESCUE_S: bajar umbrales a la mitad.
                    self._spki *= 0.5
                    self._npki *= 0.5
                    self._ref = idx
            self._m2, self._m1 = self._m1, cur
        self.n = base + len(x)
        return found

    def _candidate(self, p: int, v: float, found: list) -> None:
        thr = self._npki + 0.25 * (self._spki - self._npki)
        refr_ok = self._last_r is None or p - self._last_r >= self._refractory
        if v > thr and refr_ok:
            self._spki = 0.125 * v + 0.875 * self._spki
            r = self._locate(p)
            if self._last_r is not None:
                rr = (r - self._last_r) / self._fs
                if rr > config.RR_MAX_S:
                    self._rr.clear()
                elif rr >= config.RR_MIN_S:
                    self._rr.append(r - self._last_r)
            self._last_r = r
            self._ref = p
            self.peaks.append(r)
            found.append(r)
        else:
            self._npki = 0.125 * v + 0.875 * self._npki

    def _locate(self, p: int) -> int:
        """Posición del R: máxima desviación respecto a la mediana, en los QRS_SEARCH_S previos a p."""
        lo = max(p - self._search, self._hist_start) - self._hist_start
        hi = p - self._hist_start + 1
        seg = self._hist[lo:hi]
        if seg.size == 0:
            return p
        return self._hist_start + lo + int(np.argmax(np.abs(seg - np.median(seg))))