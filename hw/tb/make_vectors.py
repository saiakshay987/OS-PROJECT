# make test vectors for simulation (run on any machine with Python)
import numpy as np, soundfile as sf
x, sr = sf.read("common/test_wavs/up_01.wav", dtype="int16")    # 16 kHz mono
frame = x[8000:8512]                                             # one 512-sample frame
np.savetxt("hw/sim/in.hex", (frame.astype(np.int32) & 0xFFFF), fmt="%08x")
ref = np.fft.fft(frame.astype(np.float64))
np.save("hw/sim/ref_fft.npy", ref)
# after simulation, load out.hex, rebuild complex numbers, multiply by the scaling factor
# from your scaling schedule, and compare with ref (correlation > 0.99 is a pass)
