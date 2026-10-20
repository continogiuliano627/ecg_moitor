from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot

from . import config


class _Worker(QObject):
    block_ready = Signal(object)   # np.ndarray
    info = Signal(object)          # dict (solo fuentes que implementan info())
    error = Signal(str)

    def __init__(self, source):
        super().__init__()
        self._source = source
        self._timer = None

    @Slot()
    def start(self):
        # El QTimer se crea aquí para que pertenezca al hilo del worker.
        try:
            if self._timer is None:
                self._timer = QTimer()
                self._timer.setInterval(config.ACQ_INTERVAL_MS)
                self._timer.timeout.connect(self._poll)
            self._source.start()
        except Exception as e:
            self._halt()
            self.error.emit(f"{type(e).__name__}: {e}")
            return
        self._timer.start()

    @Slot()
    def stop(self):
        self._halt()

    def _halt(self):
        """Idempotente."""
        if self._timer is not None:
            self._timer.stop()
        try:
            self._source.stop()
        except Exception:
            pass

    def _poll(self):
        try:
            block = self._source.read()
            info_fn = getattr(self._source, "info", None)
            info = info_fn() if info_fn else None
        except Exception as e:
            self._halt()
            self.error.emit(f"{type(e).__name__}: {e}")
            return
        if info is not None:
            self.info.emit(info)       # antes del bloque: la GUI reinicia el filtro si hubo pérdidas
        if len(block):
            self.block_ready.emit(block)


class AcquisitionController(QObject):
    """Aloja la fuente en un QThread. Un controlador por conexión."""

    block_ready = Signal(object)
    info = Signal(object)
    error = Signal(str)
    _sig_start = Signal()

    def __init__(self, source, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _Worker(source)
        self._worker.moveToThread(self._thread)
        self._sig_start.connect(self._worker.start)
        self._worker.block_ready.connect(self.block_ready)
        self._worker.info.connect(self.info)
        self._worker.error.connect(self.error)
        self._thread.start()

    def start(self):
        self._sig_start.emit()

    def shutdown(self):
        # Bloqueante: garantiza que el puerto se cerró antes de terminar el hilo.
        QMetaObject.invokeMethod(self._worker, "stop",
                                 Qt.ConnectionType.BlockingQueuedConnection)
        self._thread.quit()
        self._thread.wait()