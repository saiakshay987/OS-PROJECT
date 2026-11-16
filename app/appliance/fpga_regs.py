# app/appliance/fpga_regs.py — register access to the HLS block through UIO.   Owner: P1
# BOARD ONLY and UNTESTED: the offsets below are placeholders. After 'export_design', copy the real ones from
# <hls project>/sol1/impl/misc/drivers/qmlp_v1_0/src/xqmlp_hw.h and delete this warning.
import mmap, os, struct
CTRL, SCORE, ATTACK, MODEL_ID, X_BASE = 0x00, 0x10, 0x20, 0x30, 0x40      # <-- replace with xqmlp_hw.h values
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
