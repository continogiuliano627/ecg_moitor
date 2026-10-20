FS = 250                 # Hz, frecuencia de muestreo
WINDOW_S = 10            # segundos visibles
BUFFER_SIZE = FS * WINDOW_S
REFRESH_HZ = 40          # refresco gráfico, independiente del muestreo
ACQ_INTERVAL_MS = 20     # periodo de sondeo del hilo de adquisición
ADC_MAX = 1023           # ADC de 10 bits del ATmega328P

MAINS_HZ = 50.0          # frecuencia de red: 50 o 60 según el país
HP_HZ = 0.5
HP_ORDER = 4
LP_HZ = 40.0
LP_ORDER = 4
NOTCH_Q = 30.0           # ancho de banda del notch ≈ MAINS_HZ / NOTCH_Q
Y_FILT_RANGE = 400       # semirrango del eje Y para señal centrada en 0

BAUD = 115200
SERIAL_BOOT_S = 2.0      # descarte tras abrir el puerto (reinicio del Nano por DTR)

QRS_BAND_LO = 5.0
QRS_BAND_HI = 15.0
QRS_MA_S = 0.100         # ventana de integración
QRS_REFRACTORY_S = 0.25
QRS_SEARCH_S = 0.12      # ventana de búsqueda del R antes del pico integrado
QRS_LEARN_S = 2.0
QRS_RESCUE_S = 2.5       # sin detecciones: umbrales a la mitad
QRS_MIN_SNR = 3.0        # SPKI/NPKI mínimo para informar frecuencia
RR_MIN_S = 0.30
RR_MAX_S = 2.00
RR_HISTORY = 8