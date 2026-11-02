# app/board/dma_test.py — AXI DMA (simple mode, no scatter-gather) driven from user space via UIO
import mmap, os, struct, time, numpy as np

def uio_by_name(name):
    for d in os.listdir("/sys/class/uio"):
        if open(f"/sys/class/uio/{d}/name").read().strip() == name:
            return f"/dev/{d}"
    raise SystemExit(f"no uio named {name}")

def open_map(dev, size):
    fd = os.open(dev, os.O_RDWR | os.O_SYNC)
    return mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=0)

regs = open_map(uio_by_name("dma"), 0x10000)          # names = DT node names; check yours
buf  = open_map(uio_by_name("audio_dma_buf"), 0x01000000)
BUF_PHYS = 0x1F000000
TX_OFF, RX_OFF = 0x000000, 0x100000

def w(off, val): regs[off:off+4] = struct.pack("<I", val)
def r(off): return struct.unpack("<I", regs[off:off+4])[0]

# PG021 register map (simple mode)
MM2S_DMACR, MM2S_DMASR, MM2S_SA, MM2S_LENGTH = 0x00, 0x04, 0x18, 0x28
S2MM_DMACR, S2MM_DMASR, S2MM_DA, S2MM_LENGTH = 0x30, 0x34, 0x48, 0x58

def reset():
    w(MM2S_DMACR, 1 << 2); w(S2MM_DMACR, 1 << 2)
    while r(MM2S_DMACR) & 4 or r(S2MM_DMACR) & 4: pass

def fft_frame(samples_i16):
    n = len(samples_i16)                            # 512
    # FFT IP input word = {imag[31:16], real[15:0]}; imag = 0
    words = samples_i16.astype("<i2").astype("<u4") & 0xFFFF
    buf[TX_OFF:TX_OFF + 4*n] = words.astype("<u4").tobytes()
    w(S2MM_DMACR, 1); w(S2MM_DA, BUF_PHYS + RX_OFF); w(S2MM_LENGTH, 4*n)   # arm receive first
    w(MM2S_DMACR, 1); w(MM2S_SA, BUF_PHYS + TX_OFF); w(MM2S_LENGTH, 4*n)   # then send
    t0 = time.time()
    while not (r(S2MM_DMASR) & (1 << 1)):           # bit1 = Idle (transfer done)
        if time.time() - t0 > 0.5: raise RuntimeError(f"timeout SR={r(S2MM_DMASR):#x}")
    out = np.frombuffer(buf[RX_OFF:RX_OFF + 4*n], dtype="<i2").reshape(n, 2)
    return out[:, 0].astype(np.float32) + 1j * out[:, 1].astype(np.float32)

reset()
x = (np.sin(2*np.pi*1000*np.arange(512)/16000) * 8000).astype(np.int16)  # 1 kHz tone
X = fft_frame(x)
print("peak bin:", int(np.argmax(np.abs(X[:257]))), "(expect 32 = 1000 Hz / 31.25 Hz)")
