from serial.tools import list_ports
import time
puertos = list_ports.comports()

if not puertos:
    print("No se detectó ningún puerto COM.")
    raise SystemExit(1)

for p in puertos:
    vid = f"{p.vid:04X}" if p.vid is not None else "N/D"
    pid = f"{p.pid:04X}" if p.pid is not None else "N/D"
    print(p.device)
    print(f"  Descripción : {p.description}")
    print(f"  Fabricante  : {p.manufacturer}")
    print(f"  VID:PID     : {vid}:{pid}")
    print(f"  Serie       : {p.serial_number}")
    print(f"  HWID        : {p.hwid}")
    print()
    
time.sleep(5.5)