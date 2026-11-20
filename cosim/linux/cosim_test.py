#!/usr/bin/env python3
# Check C: read the m0 score for every canary record through the (simulated) HLS IP and compare with qmlp.py.
# Runs in the PetaLinux guest (Python 3 + NumPy only) and on the laptop (--simulate, no /dev/mem).
#   guest:  sudo python3 cosim_test.py --base 0x43C00000 --canary /opt/ids/pool-factory/canary.npz
#   laptop: python3 cosim/linux/cosim_test.py --simulate --canary models/pool/canary.npz --model models/pool/m0.npz
# Register map (cosim/NOTES.md): AP_CTRL 0x00 (bit0 start, bit1 done, bit2 idle), SCORE 0x10, ATTACK 0x20,
# MODEL_ID 0x30, X 0x40..0x7f (4 bytes per word, little-endian). Only offsets 0x00-0x7f are used.
import argparse, mmap, os, struct, sys, time
import numpy as np

CTRL, SCORE, ATTACK, MODEL_ID, X_BASE, N_IN = 0x00, 0x10, 0x20, 0x30, 0x40, 61


class DevMem:
    """32-bit register access through /dev/mem (word loads/stores, not byte slices)."""
    def __init__(self, base, size=0x10000):
        fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
        self.m = mmap.mmap(fd, size, offset=base)
        os.close(fd)
        self.w = memoryview(self.m).cast("I")

    def read32(self, off): return self.w[off // 4]
    def write32(self, off, v): self.w[off // 4] = v & 0xFFFFFFFF


class FakeIP:
    """Laptop stand-in that follows the register map; the score is computed from the words that were written."""
    def __init__(self, model, corrupt=False):
        self.model, self.corrupt, self.words, self.done, self.res = model, corrupt, [0] * 16, False, 0

    def read32(self, off):
        if off == CTRL:
            v = 0x2 | 0x4 if self.done else 0x4
            self.done = False
            return v
        if off == SCORE: return self.res & 0xFFFFFFFF
        if off == ATTACK: return int(self.res > self.model.thr)
        if off == MODEL_ID: return 0
        return 0

    def write32(self, off, v):
        if X_BASE <= off < X_BASE + 64: self.words[(off - X_BASE) // 4] = v
        elif off == CTRL and v & 1:
            x = np.frombuffer(struct.pack("<16I", *self.words), np.uint8)[:N_IN]
            self.res = int(self.model.score(x[None, :])[0]) + (1 if self.corrupt else 0)
            self.done = True


def run_one(io, x, timeout):
    b = bytes(x) + b"\0" * (64 - len(x))
    for i, wd in enumerate(struct.unpack("<16I", b)):
        io.write32(X_BASE + 4 * i, wd)
    io.write32(CTRL, 1)  # ap_start
    t0, polls = time.time(), 0
    while True:
        c = io.read32(CTRL); polls += 1  # reading clears ap_done (clear-on-read)
        if c & 2: break
        if time.time() - t0 > timeout: raise TimeoutError("ap_done not set after %ds (AP_CTRL=0x%x)" % (timeout, c))
    sc = io.read32(SCORE)
    if sc & 0x80000000: sc -= 1 << 32  # signed int32
    return sc, io.read32(ATTACK) & 0xFF, io.read32(MODEL_ID), polls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="0x43C00000")
    ap.add_argument("--canary", default="/opt/ids/pool-factory/canary.npz")
    ap.add_argument("--model", default="/opt/ids/pool-factory/m0.npz")
    ap.add_argument("--qmlp-dir", default=None, help="directory with qmlp.py (default /opt/ids, else ../../common)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N records")
    ap.add_argument("--timeout", type=int, default=120, help="seconds to wait for ap_done per record")
    ap.add_argument("--simulate", action="store_true", help="laptop: no /dev/mem, use a Python stand-in for the IP")
    ap.add_argument("--corrupt", action="store_true", help="with --simulate: make the stand-in wrong (test the MISMATCH path)")
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    qdir = a.qmlp_dir or ("/opt/ids" if os.path.exists("/opt/ids/qmlp.py") else os.path.join(here, "..", "..", "common"))
    sys.path.insert(0, qdir)
    from qmlp import QMLP
    model = QMLP.load(a.model)
    c = np.load(a.canary, allow_pickle=False)
    X = c["X"].astype(np.uint8)
    if a.limit: X = X[:a.limit]
    exp_score = model.score(X.astype(np.int64))
    exp_attack = (exp_score > model.thr).astype(int)

    io = FakeIP(model, a.corrupt) if a.simulate else DevMem(int(a.base, 0))
    ctrl = io.read32(CTRL)
    print("AP_CTRL = 0x%08x (ap_idle bit2 %s)" % (ctrl, "set" if ctrl & 4 else "NOT SET"))
    print("model %s thr=%d, %d records" % (os.path.basename(a.model), model.thr, len(X)))

    bad = 0
    for i, x in enumerate(X):
        try:
            sc, atk, mid, polls = run_one(io, x, a.timeout)
        except TimeoutError as e:
            print("rec %2d  TIMEOUT: %s" % (i, e)); bad += 1; break
        ok = sc == int(exp_score[i]) and atk == int(exp_attack[i]) and mid == 0
        bad += not ok
        print("rec %2d  got %6d/atk %d/id %d   expected %6d/atk %d   %s  (%d polls)" %
              (i, sc, atk, mid, int(exp_score[i]), int(exp_attack[i]), "MATCH" if ok else "MISMATCH", polls))
    n = len(X)
    print("SUMMARY: %d records, %d match, %d mismatch -> %s" % (n, n - bad, bad, "PASS" if not bad and n else "FAIL"))
    return 1 if bad or not n else 0


if __name__ == "__main__":
    sys.exit(main())
