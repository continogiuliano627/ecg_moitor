import time

from ecg_app.beep import HeartBeeper

b = HeartBeeper()
if not b.available:
    print("winsound no disponible: solo Windows.")
    raise SystemExit(1)

print("10 pitidos a 72 lpm...")
for _ in range(10):
    b.play()
    time.sleep(60 / 72)
b.stop()