# app/laptop/sim_board.py — behaves exactly like the board: same features, same VAD, same messages
import sys, time, struct, queue, numpy as np, sounddevice as sd, paho.mqtt.client as mqtt
sys.path.insert(0, "common"); from features import mel_energies, Vad, SR, EPS

q = queue.Queue()
sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=SR // 2,
               callback=lambda d, *_: q.put(d[:, 0].copy())).start()
cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2); cli.connect("127.0.0.1", 1883); cli.loop_start()

vad, ring, seq = Vad(), np.zeros(SR, np.int16), 0
ring[SR // 2:] = q.get()                                  # first half second
while True:
    ring = np.concatenate([ring[SR // 2:], q.get()]); seq += 1      # slide by 0.5 s
    mel = mel_energies(ring); v = vad.update(mel)
    print(f"gate {int(v['speech'])}  speech frames {v['n_speech']:2d}  floor {v['nf_db']:.1f} dB")
    if v["speech"]:
        hdr = struct.pack("<QIHH", int(time.time() * 1000), seq, v["n_speech"], 1)
        cli.publish("pynq/features", hdr + np.log(mel + EPS).astype(np.float32).tobytes())
