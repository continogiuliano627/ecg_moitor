import os
import platform
import struct
import sys
from importlib import metadata

# Sin ventana real: solo se valida que Qt y pyqtgraph se inicializan.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

print(f"Python       : {sys.version.split()[0]}")
print(f"Ejecutable   : {sys.executable}")
print(f"Arquitectura : {struct.calcsize('P') * 8} bits")
print(f"SO           : {platform.platform()}")
print(f"Dentro de venv: {sys.prefix != sys.base_prefix}")
print()

paquetes = ["PySide6-Essentials", "shiboken6", "pyqtgraph", "pyserial", "numpy", "scipy"]
for p in paquetes:
    try:
        print(f"{p:<20} {metadata.version(p)}")
    except metadata.PackageNotFoundError:
        print(f"{p:<20} NO INSTALADO")

errores = 0


def prueba(nombre, fn):
    global errores
    try:
        resultado = fn()
        print(f"[OK]    {nombre}" + (f": {resultado}" if resultado else ""))
    except Exception as e:
        errores += 1
        print(f"[ERROR] {nombre}: {type(e).__name__}: {e}")


def t_qt():
    from PySide6.QtCore import qVersion
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    return f"Qt {qVersion()}"


def t_pyqtgraph():
    import pyqtgraph as pg
    QApp = __import__("PySide6.QtWidgets", fromlist=["QApplication"]).QApplication
    app = QApp.instance() or QApp([])
    w = pg.PlotWidget()
    w.plot([0, 1, 2], [0, 1, 0])
    app.processEvents()
    return f"binding {pg.Qt.QT_LIB}"


def t_serial():
    import serial
    from serial.tools import list_ports
    list_ports.comports()
    return f"pyserial {serial.VERSION}"


def t_dsp():
    import numpy as np
    from scipy.signal import butter, sosfilt, sosfilt_zi
    sos = butter(4, [0.5, 40], btype="bandpass", fs=250, output="sos")
    zi = sosfilt_zi(sos) * 0.0
    y, _ = sosfilt(sos, np.random.randn(250), zi=zi)
    return f"filtro SOS de {sos.shape[0]} secciones, salida {y.shape}"


prueba("PySide6 / Qt", t_qt)
prueba("pyqtgraph", t_pyqtgraph)
prueba("pyserial", t_serial)
prueba("NumPy + SciPy (filtro Butterworth 0.5-40 Hz @ 250 Hz)", t_dsp)

sys.exit(1 if errores else 0)