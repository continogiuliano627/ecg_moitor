import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QVBoxLayout, QWidget)
from serial.tools import list_ports

from . import config
from .acquisition import AcquisitionController
from .buffer import RingBuffer
from .dsp import ECGFilter
from .sources import SerialSource, SimulatedECGSource
from .hr import RPeakDetector


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor ECG educativo")
        self.resize(1000, 600)

        self._raw = RingBuffer(config.BUFFER_SIZE)
        self._filt = RingBuffer(config.BUFFER_SIZE)
        self._filter = ECGFilter()
        self._det = RPeakDetector()
        self._acq = None
        self._info = {}
        self._last_lost = 0
        self._last_error = ""

        self._plot = pg.PlotWidget()
        self._plot.setBackground("k")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("bottom", "Tiempo", units="s")
        self._plot.setXRange(-config.WINDOW_S, 0, padding=0)
        self._plot.setMouseEnabled(False, False)
        self._plot.hideButtons()
        self._curve_raw = self._plot.plot(pen=pg.mkPen("#9e9e9e", width=1))
        self._curve_filt = self._plot.plot(pen=pg.mkPen("#00e676", width=1.5))        
        self._peaks = pg.ScatterPlotItem(size=9, brush=pg.mkBrush("#ff5252"),
                                         pen=pg.mkPen(None))
        self._plot.addItem(self._peaks)

        # --- Fuente y puerto ---
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(320)
        self._btn_refresh = QPushButton("Actualizar puertos")
        self._btn_refresh.clicked.connect(self._refresh_ports)
        self._refresh_ports()

        # --- Filtros y vista ---
        self._chk_hp = QCheckBox(f"Pasa-alto {config.HP_HZ:g} Hz")
        self._chk_notch = QCheckBox(f"Notch {config.MAINS_HZ:g} Hz")
        self._chk_lp = QCheckBox(f"Pasa-bajo {config.LP_HZ:g} Hz")
        for chk in (self._chk_hp, self._chk_notch, self._chk_lp):
            chk.setChecked(True)
            chk.toggled.connect(self._on_filter_changed)

        self._view = QComboBox()
        self._view.addItems(["Filtrado", "Crudo", "Ambos"])
        self._view.currentIndexChanged.connect(self._apply_view)

        self._btn = QPushButton("Conectar")
        self._btn.setCheckable(True)
        self._btn.toggled.connect(self._on_toggle)
        self._leads = QLabel("Electrodos: N/D")
        self._hr = QLabel("FC: --")
        self._status = QLabel("Desconectado")

        row_port = QHBoxLayout()
        row_port.addWidget(QLabel("Fuente:"))
        row_port.addWidget(self._port_combo)
        row_port.addWidget(self._btn_refresh)
        row_port.addStretch(1)

        row_filters = QHBoxLayout()
        for w in (self._chk_hp, self._chk_notch, self._chk_lp):
            row_filters.addWidget(w)
        row_filters.addStretch(1)
        row_filters.addWidget(QLabel("Vista:"))
        row_filters.addWidget(self._view)

        layout = QVBoxLayout()
        layout.addLayout(row_port)
        layout.addWidget(self._plot, stretch=1)
        layout.addLayout(row_filters)
        layout.addWidget(self._btn)
        layout.addWidget(self._leads)
        layout.addWidget(self._hr)
        layout.addWidget(self._status)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self._apply_view()

        self._rate_t0 = time.perf_counter()
        self._rate_n = 0
        self._rate = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // config.REFRESH_HZ)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ---------- puertos ----------
    def _refresh_ports(self):
        current = self._port_combo.currentData()
        self._port_combo.clear()
        self._port_combo.addItem("Simulada", None)
        for p in sorted(list_ports.comports(), key=lambda p: p.device):
            self._port_combo.addItem(f"{p.device} - {p.description}", p.device)
        idx = self._port_combo.findData(current)
        if idx >= 0:
            self._port_combo.setCurrentIndex(idx)

    # ---------- vista y filtros ----------
    def _apply_view(self, *_):
        mode = self._view.currentText()
        self._curve_raw.setVisible(mode in ("Crudo", "Ambos"))
        self._curve_filt.setVisible(mode in ("Filtrado", "Ambos"))
        if mode == "Crudo":
            self._plot.setYRange(0, config.ADC_MAX, padding=0)
            self._plot.setLabel("left", "ADC (cuentas)")
        else:
            self._plot.setYRange(-config.Y_FILT_RANGE, config.Y_FILT_RANGE, padding=0)
            self._plot.setLabel("left", "ADC (cuentas, sin offset)")

    def _on_filter_changed(self, _checked: bool):
        self._filter.configure(self._chk_hp.isChecked(),
                               self._chk_lp.isChecked(),
                               self._chk_notch.isChecked())
        self._filt.clear()

    # ---------- conexión ----------
    def _on_toggle(self, running: bool):
        if running:
            device = self._port_combo.currentData()
            source = (SerialSource(device) if device
                      else SimulatedECGSource(mains_hz=config.MAINS_HZ))
            self._raw.clear()
            self._filt.clear()
            self._filter.reset()
            self._det.reset()
            self._info = {}
            self._last_lost = 0
            self._last_error = ""
            self._rate_t0 = time.perf_counter()
            self._rate_n = 0
            self._rate = 0.0
            self._port_combo.setEnabled(False)
            self._btn_refresh.setEnabled(False)
            self._btn.setText("Desconectar")
            self._acq = AcquisitionController(source)
            self._acq.block_ready.connect(self._on_block)
            self._acq.info.connect(self._on_info)
            self._acq.error.connect(self._on_error)
            self._acq.start()
        else:
            if self._acq is not None:
                self._acq.shutdown()
                self._acq = None
            self._port_combo.setEnabled(True)
            self._btn_refresh.setEnabled(True)
            self._btn.setText("Conectar")
            self._refresh_ports()

    def _on_error(self, msg: str):
        self._last_error = msg
        if self._btn.isChecked():
            self._btn.setChecked(False)     # dispara _on_toggle(False)

    # ---------- datos ----------
    def _on_info(self, info: dict):
        self._info = info
        lost = info.get("lost", 0)
        if lost > self._last_lost:
            self._filter.reset()            # el filtro asume muestras contiguas
            self._det.resync()              # el detector también
        self._last_lost = lost

    def _on_block(self, block: np.ndarray):
        self._det.process(block)
        self._filt.append(self._filter.process(block))
        self._raw.append(block)
        self._rate_n += len(block)

    @staticmethod
    def _draw(curve, data: np.ndarray):
        n = len(data)
        if n:
            x = (np.arange(n) - n) / config.FS
            curve.setData(x, data, skipFiniteCheck=True)
    def _update_peaks(self, mode: str, raw: np.ndarray):
        # Los índices del detector son absolutos; se alinean contra el final del búfer.
        arr = raw if mode == "Crudo" else self._filt.snapshot()
        nb = len(arr)
        xs, ys = [], []
        for idx in self._det.peaks:
            pos = nb - (self._det.n - idx)
            if 0 <= pos < nb:
                xs.append((pos - nb) / config.FS)
                ys.append(arr[pos])
        self._peaks.setData(x=xs, y=ys)

    def _update_hr(self):
        if not self._btn.isChecked():
            self._hr.setText("FC: --")
        elif self._info.get("lo_plus") or self._info.get("lo_minus"):
            self._hr.setText("FC: -- (electrodos desconectados)")
        elif self._det.learning:
            self._hr.setText("FC: calibrando...")
        elif self._det.bpm is None:
            self._hr.setText(f"FC: -- (señal insuficiente, SNR {self._det.snr:.1f})")
        else:
            self._hr.setText(f"FC: {self._det.bpm:.0f} lpm")
    def _refresh(self):
        now = time.perf_counter()
        if now - self._rate_t0 >= 1.0:
            self._rate = self._rate_n / (now - self._rate_t0)
            self._rate_t0, self._rate_n = now, 0

        mode = self._view.currentText()
        raw = self._raw.snapshot()
        if mode in ("Crudo", "Ambos") and len(raw):
            self._draw(self._curve_raw, raw if mode == "Crudo" else raw - raw.mean())
        if mode in ("Filtrado", "Ambos"):
            self._draw(self._curve_filt, self._filt.snapshot())

        if self._btn.isChecked():
            texto = f"Conectado | tasa efectiva: {self._rate:.1f} Hz | búfer: {len(raw)}"
            if self._info:
                i = self._info
                texto += (f" | tramas: {i['frames']} | perdidas: {i['lost']} | "
                          f"checksum: {i['bad']} | bytes descartados: {i['discarded']}")
        else:
            texto = "Desconectado"
            if self._last_error:
                texto += f" | ERROR: {self._last_error}"
        self._status.setText(texto)

        if self._btn.isChecked() and self._info:
            off = self._info["lo_plus"] or self._info["lo_minus"]
            self._leads.setText("Electrodos: DESCONECTADOS (LO+/LO-)" if off
                                else "Electrodos: conectados")
        else:
            self._leads.setText("Electrodos: N/D")

        self._update_peaks(mode, raw)
        self._update_hr()

    def closeEvent(self, event):
        self._timer.stop()
        if self._acq is not None:
            self._acq.shutdown()
            self._acq = None
        super().closeEvent(event)