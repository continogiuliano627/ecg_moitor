import numpy as np
from scipy.signal import sosfreqz

from ecg_app import config
from ecg_app.dsp import ECGFilter

rng = np.random.default_rng(0)
fallos = 0


def verificar(nombre, ok, detalle=""):
    global fallos
    fallos += 0 if ok else 1
    print(f"[{'OK' if ok else 'ERROR'}] {nombre} {detalle}")


# 1. Invariancia al tamaño de bloque (valida la persistencia del estado)
x = 512 + rng.normal(0, 20, 5000)
y_full = ECGFilter().process(x)
f = ECGFilter()
partes, i = [], 0
while i < len(x):
    n = int(rng.integers(1, 51))
    partes.append(f.process(x[i:i + n]))
    i += n
verificar("Invariancia al tamaño de bloque", np.allclose(y_full, np.concatenate(partes)),
          f"(máx. dif. {np.max(np.abs(y_full - np.concatenate(partes))):.2e})")

# 2. Respuesta en frecuencia de la cascada
sos = ECGFilter().sos
frecs = np.array([0.3, 10.0, config.MAINS_HZ, 100.0])
_, h = sosfreqz(sos, worN=frecs, fs=config.FS)
g = np.abs(h)
db = 20 * np.log10(g)
for fr, gi, d in zip(frecs, g, db):
    print(f"        {fr:>6.1f} Hz: ganancia {gi:.4f} ({d:+.1f} dB)")
verificar("0.3 Hz ≈ 0.13", 0.10 < g[0] < 0.16)
verificar("10 Hz dentro de ±0.5 dB", abs(db[1]) < 0.5)
verificar("Red atenuada > 30 dB", db[2] < -30)
verificar("100 Hz atenuada > 25 dB", db[3] < -25)

# 3. Entrada constante: sin transitorio
y = ECGFilter().process(np.full(500, 512.0))
verificar("Entrada constante 512 → salida ≈ 0", np.max(np.abs(y)) < 1e-6,
          f"(máx. |y| = {np.max(np.abs(y)):.2e})")

# 4. Estabilidad con 1e6 muestras
y = ECGFilter().process(512 + rng.normal(0, 50, 1_000_000))
verificar("Estabilidad 1e6 muestras", np.all(np.isfinite(y)) and np.max(np.abs(y)) < 1000,
          f"(máx. |y| = {np.max(np.abs(y)):.1f})")

raise SystemExit(1 if fallos else 0)