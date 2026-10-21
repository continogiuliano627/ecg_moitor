// ECG educativo: AD8232 -> A0, LO+ -> D10, LO- -> D11. 250 Hz, 115200 baudios.
// Trama: [0xAA][cnt][lo][hi][estado][cnt^lo^hi^estado]; estado bit0=LO+, bit1=LO-.
#include <Arduino.h>

const uint8_t PIN_ECG = A0;
const uint8_t PIN_LO_P = 10;
const uint8_t PIN_LO_N = 11;

volatile uint16_t g_sample = 0;
volatile uint8_t g_status = 0;
volatile uint8_t g_counter = 0;
volatile bool g_ready = false;

ISR(TIMER1_COMPA_vect) {
  g_sample = analogRead(PIN_ECG);
  g_status = (digitalRead(PIN_LO_P) ? 0x01 : 0x00) | (digitalRead(PIN_LO_N) ? 0x02 : 0x00);
  g_counter++;  // si loop() no envía a tiempo, el hueco se ve como pérdida
  g_ready = true;
}

void setup() {
  pinMode(PIN_LO_P, INPUT);
  pinMode(PIN_LO_N, INPUT);
  analogReference(EXTERNAL);  // solo si 3V3 está conectado a AREF
  analogRead(PIN_ECG);        // descarta la primera lectura tras cambiar la referencia
  Serial.begin(115200);

  noInterrupts();
  TCCR1A = 0;
  TCCR1B = (1 << WGM12) | (1 << CS11) | (1 << CS10);  // CTC, prescaler 64 -> 250 kHz
  OCR1A = 999;                                        // 250 kHz / 1000 = 250 Hz
  TCNT1 = 0;
  TIMSK1 = (1 << OCIE1A);
  interrupts();
}

void loop() {
  if (!g_ready) return;

  noInterrupts();
  uint16_t s = g_sample;
  uint8_t st = g_status;
  uint8_t c = g_counter;
  g_ready = false;
  interrupts();

  uint8_t lo = s & 0xFF, hi = s >> 8;
  uint8_t f[6] = { 0xAA, c, lo, hi, st, (uint8_t)(c ^ lo ^ hi ^ st) };
  Serial.write(f, 6);
}