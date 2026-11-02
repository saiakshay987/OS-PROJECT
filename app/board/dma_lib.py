# app/board/dma_lib.py — the FPGA backend that frontend.py (P2) calls. P1 owns this file.
# Move the open_map / w / r helpers from dma_test.py into small UioRegs / UioBuf classes.
import numpy as np, struct
from features import frame, HANN, MEL_FB, Vad          # v1 finishes power/mel/VAD on the ARM

# Register offsets: copy them from the exported IP's driver header
#   hw/hls/<solution>/impl/ip/drivers/mel_frontend_v1_0/src/xmel_frontend_hw.h
# The numbers below are PLACEHOLDERS — yours will differ.
AP_CTRL, N_FRAMES, MARGIN, MIN_FRAMES, HANG, RESET = 0x00, 0x10, 0x18, 0x20, 0x28, 0x30
GATE, N_SPEECH, NOISE_FLOOR = 0x38, 0x48, 0x58
NEPER_PER_DB = np.log(10) / 10

class FpgaFrontend:
    def __init__(self, margin_db=9.0, min_frames=5, hang=1, version=2):
        self.v = version
        self.dma, self.buf = UioRegs("dma"), UioBuf("audio_dma_buf")
        if version == 2:
            self.hls = UioRegs("mel_frontend")
            self.hls.w(N_FRAMES, 49); self.hls.w(MIN_FRAMES, min_frames); self.hls.w(HANG, hang)
            self.hls.w(MARGIN, struct.unpack("<I", struct.pack("<f", margin_db * NEPER_PER_DB))[0])
            self.hls.w(RESET, 1); self.first = True
        else:
            self.vad = Vad(margin_db=margin_db, min_frames=min_frames, hang=hang)

    def process(self, ring):                     # ring: 16000 int16 → (mel (49,40), vad dict)
        frames = frame(ring)                     # (49, 512) overlapping frames, exactly as features.py
        if self.v == 1:                          # FFT IP: window on ARM, 49 small DMA transfers
            spec = np.stack([fft_frame((f * HANN).astype(np.int16)) for f in frames])
            mel = (spec.real[:, :257] ** 2 + spec.imag[:, :257] ** 2) @ MEL_FB.T
            v = self.vad.update(mel); v["hw"] = False
            return mel, v
        self.buf.write_tx((frames.astype(np.int32) & 0xFFFF).astype("<u4"))  # 1 sample / word
        self.hls.w(AP_CTRL, 1)                                               # ap_start
        self.dma.start_s2mm(RX_PHYS, 49 * 40 * 4)                            # arm receive first
        self.dma.start_mm2s(TX_PHYS, 49 * 512 * 4)                           # then send
        self.dma.wait_s2mm()
        while not self.hls.r(AP_CTRL) & 0x2: pass                            # ap_done
        if self.first: self.hls.w(RESET, 0); self.first = False             # reset only once
        mel = self.buf.read_rx(49 * 40, "<f4").reshape(49, 40)
        nf = struct.unpack("<f", struct.pack("<I", self.hls.r(NOISE_FLOOR)))[0]
        return mel, {"speech": bool(self.hls.r(GATE)), "n_speech": self.hls.r(N_SPEECH),
                     "nf_db": nf / NEPER_PER_DB, "hw": True}
