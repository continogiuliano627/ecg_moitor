import argparse
import sys
import time

import serial
from serial.tools import list_ports

ap = argparse.ArgumentParser()
ap.add_argument("--port", help="Nombre del puerto, p. ej. COM5")
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--ciclos", type=int, default=5, help="Ciclos de apertura/cierre")
args = ap.parse_args()

puertos = [p.device for p in list_ports.comports()]
puerto = args.port
if puerto is None:
    if len(puertos) == 1:
        puerto = puertos[0]
        print(f"Puerto único detectado, se usa {puerto}")
    else:
        print(f"Especificar --port. Disponibles: {puertos or 'ninguno'}")
        sys.exit(2)

try:
    # 1. Apertura, espera del reinicio por DTR y lectura pasiva.
    t0 = time.perf_counter()
    with serial.Serial(puerto, args.baud, timeout=1, write_timeout=1) as ser:
        print(f"Apertura: {time.perf_counter() - t0:.3f} s, is_open={ser.is_open}")
        time.sleep(2.0)
        ser.reset_input_buffer()
        total, t_fin = 0, time.perf_counter() + 2.0
        while time.perf_counter() < t_fin:
            total += len(ser.read(ser.in_waiting or 1))
        print(f"Bytes recibidos en 2 s: {total} "
              f"({'el firmware transmite' if total else 'sin datos: normal si no hay sketch cargado'})")
    print(f"Cierre: is_open={ser.is_open}")

    # 2. Ciclos de apertura/cierre: detecta puertos que no se liberan.
    for i in range(args.ciclos):
        s = serial.Serial(puerto, args.baud, timeout=0.5)
        s.close()
        assert not s.is_open
    print(f"{args.ciclos} ciclos apertura/cierre correctos")
    print("RESULTADO: OK")

except serial.SerialException as e:
    print(f"RESULTADO: ERROR: {e}")
    print("Acceso denegado (13) = puerto en uso por otro programa. "
          "FileNotFound (2) = el puerto ya no existe (cable desconectado o COM cambiado).")
    sys.exit(1)