
# common/make_vad_test.py — a reproducible 60 s test recording + expected gate decisions
import numpy as np, soundfile as sf, glob, random
from features import make_vad_vectors, SR
random.seed(0); rng = np.random.default_rng(0)
D = "data/SpeechCommands/speech_commands_v0.02"
words = [sf.read(random.choice(glob.glob(f"{D}/{w}/*.wav")), dtype="int16")[0]
         for w in ["up", "down", "left", "right", "stop", "go", "yes", "no", "on", "off"]]
noise = sf.read(f"{D}/_background_noise_/running_tap.wav", dtype="int16")[0]   # a 'fan'
x = (rng.normal(0, 40, 60 * SR)).astype(np.float32)          # quiet room hiss
for i, w in enumerate(words):                                # one word every 2.5 s, from 5 s
    t = int((5 + 2.5 * i) * SR); x[t:t + len(w)] += w
x[40 * SR:50 * SR] += noise[:10 * SR] * 0.5                  # 10 s of 'fan' (no speech)
for i in range(3):                                           # 3 words on top of the fan
    t = int((51 + 2.5 * i) * SR); x[t:t + len(words[i])] += words[i]
sf.write("common/test_wavs/vad_test.wav", np.clip(x, -32768, 32767).astype(np.int16), SR)
make_vad_vectors("common/test_wavs/vad_test.wav", "common/test_wavs/vad_expected.csv")
