#!/usr/bin/env python3
# app/board/frontend.py — USB mic -> features + VAD (FPGA or ARM) -> gated MQTT publish.  Owner: P2
import argparse, json, os, struct, subprocess, time
import numpy as np, paho.mqtt.client as mqtt
from features import SR, EPS, mel_energies, Vad

p = argparse.ArgumentParser()
p.add_argument("--backend", default=os.getenv("BACKEND", "fpga"), choices=["fpga", "arm"])
p.add_argument("--vad", default=os.getenv("VAD", "on"), choices=["on", "off"])
p.add_argument("--margin-db", type=float, default=float(os.getenv("VAD_MARGIN_DB", "9")))
p.add_argument("--mic", default=os.getenv("MIC_DEVICE", "plughw:1,0"))
p.add_argument("--broker", default=os.getenv("BROKER", "192.168.2.1"))
a = p.parse_args()

if a.backend == "fpga":
    from dma_lib import FpgaFrontend                       # P1's module
    fpga = FpgaFrontend(margin_db=a.margin_db)
else:
    fpga, vad = None, Vad(margin_db=a.margin_db)

def on_connect(c, userdata, flags, reason, props):
    c.subscribe("laptop/command")                          # re-subscribe after every reconnect

def on_command(c, userdata, msg):                          # round-trip latency, ends up in the journal
    d = json.loads(msg.payload)
    print(f"command {d['word']} conf {d['conf']:.2f} rtt {time.time()*1000 - d['ts']:.0f} ms", flush=True)

cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="pynq-board")
if os.getenv("MQTT_USER"):
    cli.username_pw_set(os.getenv("MQTT_USER"), os.getenv("MQTT_PASS"))
cli.on_connect, cli.on_message = on_connect, on_command
cli.connect_async(a.broker, 1883)                          # keeps retrying if the laptop isn't up yet
cli.loop_start()

rec = subprocess.Popen(["arecord", "-q", "-D", a.mic, "-f", "S16_LE", "-r", str(SR),
                        "-c", "1", "-t", "raw"], stdout=subprocess.PIPE)
HALF = SR // 2                                             # 0.5 s = 8000 samples = 16000 bytes

def read_exact(n):
    buf = b""
    while len(buf) < n:
        chunk = rec.stdout.read(n - len(buf))
        if not chunk:
            raise SystemExit("arecord stopped (mic unplugged?)")  # systemd restarts us
        buf += chunk
    return buf

ring, seq, blocks = np.zeros(SR, np.int16), 0, 0
st = dict(windows=0, published=0, proc_ms=0.0)
t_stat, cpu0 = time.time(), os.times()
while True:
    ring = np.concatenate([ring[HALF:], np.frombuffer(read_exact(2 * HALF), np.int16)])
    blocks += 1
    if blocks < 2:
        continue                                           # wait for the first full second
    t0 = time.perf_counter()
    if fpga:
        mel, v = fpga.process(ring)                        # FPGA: features + gate decision
    else:
        mel = mel_energies(ring); v = vad.update(mel); v["hw"] = False
    st["proc_ms"] += (time.perf_counter() - t0) * 1000
    seq += 1; st["windows"] += 1
    if v["speech"] or a.vad == "off":
        flags = (1 if v["speech"] else 0) | (2 if v["hw"] else 0) | (4 if a.vad == "off" else 0)
        hdr = struct.pack("<QIHH", int(time.time() * 1000), seq, v["n_speech"], flags)
        cli.publish("pynq/features", hdr + np.log(mel + EPS).astype(np.float32).tobytes())
        st["published"] += 1
    if time.time() - t_stat >= 5:                          # heartbeat every 5 s
        c1, wall = os.times(), time.time() - t_stat
        cpu = 100 * ((c1.user - cpu0.user) + (c1.system - cpu0.system)) / wall
        cli.publish("pynq/status", json.dumps({
            "uptime_s": int(time.monotonic()), "backend": a.backend, "vad": a.vad,
            "noise_floor_db": round(float(v["nf_db"]), 1), "windows": st["windows"],
            "published": st["published"], "cpu_pct": round(cpu, 1),
            "proc_ms_avg": round(st["proc_ms"] / max(1, st["windows"]), 2)}))
        st = dict(windows=0, published=0, proc_ms=0.0); t_stat, cpu0 = time.time(), c1
