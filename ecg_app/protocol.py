import numpy as np

SYNC = 0xAA
FRAME_LEN = 6        # SYNC, contador, muestra lo, muestra hi, estado, checksum
ADC_MAX = 1023


class FrameParser:
    """Reensambla tramas desde un flujo de bytes arbitrariamente fragmentado.

    Trama: [0xAA][cnt][lo][hi][estado][cnt^lo^hi^estado]
    estado: bit0 = LO+, bit1 = LO- (1 = electrodo desconectado).
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._buf = bytearray()
        self._last = None
        self.frames = 0
        self.lost = 0
        self.bad = 0
        self.discarded = 0
        self.lo_plus = False
        self.lo_minus = False

    def feed(self, data: bytes) -> np.ndarray:
        """Devuelve las muestras (float64, cuentas ADC) de las tramas completas."""
        if data:
            self._buf += data
        buf = self._buf
        n = len(buf)
        out = []
        i = 0
        while n - i >= FRAME_LEN:
            if buf[i] != SYNC:
                i += 1
                self.discarded += 1
                continue
            cnt, lo, hi, st, chk = buf[i + 1], buf[i + 2], buf[i + 3], buf[i + 4], buf[i + 5]
            sample = lo | (hi << 8)
            if (cnt ^ lo ^ hi ^ st) != chk or sample > ADC_MAX:
                # Sincronía falsa o trama corrupta: se descarta 1 byte y se resincroniza.
                self.bad += 1
                self.discarded += 1
                i += 1
                continue
            if self._last is not None:
                self.lost += (cnt - self._last - 1) & 0xFF
            self._last = cnt
            self.frames += 1
            self.lo_plus = bool(st & 0x01)
            self.lo_minus = bool(st & 0x02)
            out.append(sample)
            i += FRAME_LEN
        del buf[:i]
        return np.asarray(out, dtype=np.float64)