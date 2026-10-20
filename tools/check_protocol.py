import numpy as np

from ecg_app.protocol import SYNC, FrameParser

rng = np.random.default_rng(1)
fallos = 0


def verificar(nombre, ok, detalle=""):
    global fallos
    fallos += 0 if ok else 1
    print(f"[{'OK' if ok else 'ERROR'}] {nombre} {detalle}")


def trama(cnt, sample, st=0):
    cnt &= 0xFF
    lo, hi = sample & 0xFF, sample >> 8
    return bytes([SYNC, cnt, lo, hi, st, cnt ^ lo ^ hi ^ st])


def alimentar(parser, flujo):
    out, i = [], 0
    while i < len(flujo):
        n = int(rng.integers(1, 21))
        out.append(parser.feed(flujo[i:i + n]))
        i += n
    return np.concatenate(out)


muestras = rng.integers(0, 1024, 1000)

# 1. Ida y vuelta con fragmentación arbitraria y desborde del contador
p = FrameParser()
y = alimentar(p, b"".join(trama(i, int(m)) for i, m in enumerate(muestras)))
verificar("Ida y vuelta", np.array_equal(y, muestras), f"(tramas {p.frames})")
verificar("Sin pérdidas ni errores", p.lost == 0 and p.bad == 0 and p.discarded == 0)

# 2. Conteo de pérdidas (5 tramas omitidas)
p = FrameParser()
flujo = b"".join(trama(i, int(m)) for i, m in enumerate(muestras) if not 100 <= i < 105)
y = alimentar(p, flujo)
verificar("Pérdidas contadas", p.lost == 5 and len(y) == 995, f"(lost={p.lost})")

# 3. Basura previa: resincronización
p = FrameParser()
y = alimentar(p, b"\x01\x02\xaa\x03\x04" + b"".join(trama(i, int(m)) for i, m in enumerate(muestras)))
verificar("Resincronización tras basura", len(y) >= 999 and y[-1] == muestras[-1],
          f"(recuperadas {len(y)}, descartados {p.discarded})")

# 4. Checksum corrupto en una trama
p = FrameParser()
tramas = [bytearray(trama(i, int(m))) for i, m in enumerate(muestras)]
tramas[50][5] ^= 0xFF
y = alimentar(p, b"".join(bytes(t) for t in tramas))
verificar("Trama corrupta descartada", p.bad >= 1 and p.lost == 1 and len(y) == 999,
          f"(bad={p.bad}, lost={p.lost}, recibidas={len(y)})")

# 5. Bits de estado
p = FrameParser()
p.feed(trama(0, 500, 0b11))
verificar("Estado LO+/LO-", p.lo_plus and p.lo_minus)
p.feed(trama(1, 500, 0b00))
verificar("Estado limpio", not p.lo_plus and not p.lo_minus)

raise SystemExit(1 if fallos else 0)