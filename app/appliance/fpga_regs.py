# app/appliance/fpga_regs.py — register access to the HLS block through UIO.   Owner: P1
# The register offsets below MATCH the xqmlp_hw.h generated for m0 (see cosim/NOTES.md). That register map was exercised by the
# Verilator test of the RTL (Check R) and by /dev/mem accesses from Linux in the QEMU co-simulation (Check C, cosim/linux/cosim_test.py).
# This module itself (the UIO open and the score() loop) has NOT been run: board only and UNTESTED.
import mmap, os, struct
CTRL, SCORE, ATTACK, MODEL_ID, X_BASE = 0x00, 0x10, 0x20, 0x30, 0x40      # = XQMLP_CTRL_ADDR_{AP_CTRL,SCORE_DATA,ATTACK_DATA,MODEL_ID_DATA,X_BASE}
_m = None
def open(dev="/dev/uio0", size=0x10000):
    global _m
    fd = os.open(dev, os.O_RDWR | os.O_SYNC); _m = mmap.mmap(fd, size); os.close(fd)
def score(x):
    b = bytes(x) + b"\0" * (-len(x) % 4)
    _m[X_BASE:X_BASE + len(b)] = b                                    # the input array is a small register-mapped memory
    _m[CTRL:CTRL + 4] = struct.pack("<I", 1)                          # ap_start
    while not struct.unpack("<I", _m[CTRL:CTRL + 4])[0] & 2: pass     # wait for ap_done
    return struct.unpack("<i", _m[SCORE:SCORE + 4])[0]
def model_id(): return struct.unpack("<I", _m[MODEL_ID:MODEL_ID + 4])[0]
