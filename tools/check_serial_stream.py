import argparse
import sys
import time

import numpy as np
import serial
from serial.tools import list_ports

from ecg_app import config
from ecg_app.protocol import FrameParser


def elegir_puerto(arg):
    if arg:
        return arg
    puertos = [p.device for p in list_ports.comports()]
    if len(puertos) == 1:
        print(f"Puerto único detectado, se usa {puertos[0]}")
        return puertos[0]
    print(f"Especificar --port. Disponibles: {puertos or 'ninguno'}")
    sys.exit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="Nombre del puerto, p. ej. COM5")
    ap.add_argument("--baud", type=int, default=config.BAUD)
    ap.add_argument("--segundos", type=float, default=60.0, help="Duración de la medición")
    args = ap.parse_args()
    puerto = elegir_puerto(args.port)

    try:
        ser = serial.Serial(puerto, args.baud, timeout=0.05, write_timeout=1)
    except serial.SerialException as e:
        print(f"ERROR al abrir {puerto}: {e}")
        return 1

    try:
        # 1. Reinicio del Nano por DTR: se descarta todo durante SERIAL_BOOT_S.
        print(f"Abierto {puerto} a {args.baud}. Descartando arranque ({config.SERIAL_BOOT_S:g} s)...")
        t_boot = time.perf_counter() + config.SERIAL_BOOT_S
        while time.perf_counter() < t_boot:
            ser.read(max(1, ser.in_waiting))
        ser.reset_input_buffer()

        # 2. Medición.
        parser = FrameParser()
        bloques, total_bytes, polls, polls_off = [], 0, 0, 0
        base = None                     # (bad, discarded) tras 1 s de medición
        t0 = time.perf_counter()
        t_next = t0 + 10.0
        while True:
            now = time.perf_counter()
            if now - t0 >= args.segundos:
                break
            data = ser.read(max(1, ser.in_waiting))
            total_bytes += len(data)
            s = parser.feed(data)
            if len(s):
                bloques.append(s)
            polls += 1
            polls_off += parser.lo_plus or parser.lo_minus
            if base is None and now - t0 >= 1.0:
                base = (parser.bad, parser.discarded)
            if now >= t_next:
                print(f"  t={now - t0:5.0f} s  tramas={parser.frames}  perdidas={parser.lost}  "
                      f"checksum={parser.bad}  descartados={parser.discarded}")
                t_next += 10.0
        dt = time.perf_counter() - t0
    except serial.SerialException as e:
        print(f"ERROR durante la lectura: {e}")
        return 1
    finally:
        ser.close()

    print()
    print(f"Bytes recibidos: {total_bytes} en {dt:.1f} s ({total_bytes / dt:.0f} B/s; esperado ≈ {6 * config.FS})")
    if parser.frames == 0:
        if total_bytes:
            print("RESULTADO: ERROR: hay bytes pero ninguna trama válida. "
                  "Causa probable: baudios distintos a los del firmware o firmware con otro formato.")
        else:
            print("RESULTADO: ERROR: sin datos. Causa probable: sketch no cargado, "
                  "monitor serie del IDE abierto, o puerto equivocado.")
        return 1

    x = np.concatenate(bloques)
    rx = parser.frames / dt
    fw = (parser.frames + parser.lost) / dt
    delta_malas = (parser.bad - base[0]) + (parser.discarded - base[1]) if base else 0
    print(f"Tramas válidas        : {parser.frames}")
    print(f"Tasa recibida         : {rx:.2f} Hz")
    print(f"Tasa del firmware     : {fw:.2f} Hz  (tramas + perdidas, objetivo {config.FS})")
    print(f"Muestras perdidas     : {parser.lost}")
    print(f"Checksum / descartados: {parser.bad} / {parser.discarded} "
          f"(tras el primer segundo: {delta_malas})")
    print(f"ADC                   : mín {x.min():.0f}  máx {x.max():.0f}  "
          f"media {x.mean():.1f}  desv {x.std():.1f}")
    print(f"Electrodos desconectados en {100.0 * polls_off / max(polls, 1):.0f} % de las lecturas")

    criterios = [
        ("Tasa del firmware dentro de ±1 %", abs(fw - config.FS) <= 0.01 * config.FS),
        ("Cero muestras perdidas", parser.lost == 0),
        ("Sin tramas corruptas tras el primer segundo", delta_malas == 0),
    ]
    ok = True
    for nombre, cumple in criterios:
        print(f"[{'OK' if cumple else 'ERROR'}] {nombre}")
        ok &= cumple
    print("RESULTADO:", "OK" if ok else "ERROR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())