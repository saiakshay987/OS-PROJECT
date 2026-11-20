#!/usr/bin/env python3
# app/appliance/idsd.py — the appliance daemon.  Owner: P2 (service), P1 (FpgaBackend), P4 (pack security)
# flow records in (MQTT or UDP) -> active model classifies -> attacker's address blocked (nftables) -> alert to the
# laptop for stage 2.  A rotation policy swaps the active model; only signed, self-tested model packs are loaded.
import argparse, json, os, random, socket, struct, subprocess, sys, time
import numpy as np, paho.mqtt.client as mqtt
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "..", "..", "common")): sys.path.insert(0, p)
import modelpack

E = os.getenv
ap = argparse.ArgumentParser()
ap.add_argument("--input", default=E("INPUT", "mqtt"), choices=["mqtt", "udp"])      # mqtt works through QEMU's NAT
ap.add_argument("--port", type=int, default=int(E("LISTEN_PORT", "5555")))
ap.add_argument("--broker", default=E("BROKER", "10.0.2.2"))                         # 10.0.2.2 = the host, seen from QEMU
ap.add_argument("--pool", default=E("POOL_DIR", "/data/pool"))                       # updates land here (pool/current)
ap.add_argument("--factory", default=E("FACTORY_DIR", "/opt/ids/pool-factory"))      # known-good pack in the read-only image
ap.add_argument("--pubkey", default=E("PUBKEY", "/etc/ids/pool_pub.pem"))
ap.add_argument("--backend", default=E("BACKEND", "arm"), choices=["arm", "fpga"])
ap.add_argument("--rotate", default=E("ROTATE", "poisson"), choices=["off", "fixed", "poisson", "event"])
ap.add_argument("--rotate-s", type=float, default=float(E("ROTATE_S", "30")))        # (mean) seconds between swaps
ap.add_argument("--swap-ms", type=float, default=float(E("SWAP_MS", "207")))         # emulated reconfiguration time (arm backend)
ap.add_argument("--fallback", default=E("FALLBACK", "arm"), choices=["arm", "hold", "open"])
ap.add_argument("--block", default=E("BLOCK", "nft"), choices=["nft", "log"])
ap.add_argument("--block-ttl", default=E("BLOCK_TTL", "60s"))
ap.add_argument("--event-n", type=int, default=int(E("EVENT_N", "20")))              # 'event': this many alerts ...
ap.add_argument("--event-s", type=float, default=float(E("EVENT_S", "2")))           # ... within this many seconds
ap.add_argument("--seed", type=int, default=None)
a = ap.parse_args()
rng = random.Random(a.seed)
def log(*m): print(*m, flush=True)

# ---------------- model pack: newest valid one wins; anything unsigned / tampered / failing its self-test is skipped --
def load_pack():
    cands = []
    cur = os.path.join(a.pool, "current")
    if os.path.exists(cur): cands.append(os.path.realpath(cur))
    if os.path.isdir(a.pool):
        cands += sorted((os.path.join(a.pool, d) for d in os.listdir(a.pool) if d.startswith("v")),
                        key=lambda p: int(os.path.basename(p)[1:]) if os.path.basename(p)[1:].isdigit() else -1, reverse=True)
    cands.append(a.factory); seen = set()
    for d in cands:
        if d in seen: continue
        seen.add(d)
        try:
            models, man = modelpack.verify(d, a.pubkey)
            log(f"pack OK: {d} version {man['version']} with {len(models)} models"); return models, man, d
        except (ValueError, OSError) as e:
            log(f"pack REJECTED: {d}: {e} -> trying the next one (rollback)")
    sys.exit("no valid model pack, refusing to start")
models, manifest, pack_dir = load_pack()
N_IN = models[0].layers[0]["W"].shape[1]
REC = struct.Struct("<IIQ"); RLEN = REC.size + N_IN            # seq, source IPv4, sender timestamp (ms), then N_IN bytes

# ---------------- backends ------------------------------------------------------------------------------------------
class ArmBackend:
    """Integer inference on the CPU. With SWAP_MS > 0 it also imitates the time an FPGA takes to load a bitstream."""
    name = "arm"
    def load(self, m): self.m = m; return a.swap_ms / 1000.0          # seconds until the new model is usable
    def margins(self, X): return self.m.margin(X)

class FpgaBackend:
    """BOARD ONLY, untested until the board arrives (P1). One bitstream per model; registers from the HLS driver header."""
    name = "fpga"
    def __init__(self):
        import fpga_regs                                                # P1 provides app/appliance/fpga_regs.py
        self.io = fpga_regs
    def load(self, m):
        t = time.time(); f = m.meta["file"].replace(".npz", "")
        subprocess.run(["fpgautil", "-b", f"/lib/firmware/ids/{f}.bit.bin", "-o", "/lib/firmware/ids/qmlp.dtbo"], check=True)
        self.io.open(); self.thr = m.thr; log(f"bitstream loaded in {1000 * (time.time() - t):.0f} ms"); return 0.0
    def margins(self, X): return np.array([self.io.score(x) for x in X], np.int64) - self.thr
backend = FpgaBackend() if a.backend == "fpga" else ArmBackend()
fallback_model = models[0]                                              # fixed software model used while a swap is running

# ---------------- blocking ------------------------------------------------------------------------------------------
blocked = {}
def ip_str(u): return socket.inet_ntoa(struct.pack(">I", u))
def block(src):
    now = time.time()
    if blocked.get(src, 0) > now: return False
    blocked[src] = now + 30
    if a.block == "nft":
        r = subprocess.run(["nft", "add", "element", "inet", "filter", "blocked", f"{{ {ip_str(src)} timeout {a.block_ttl} }}"],
                           capture_output=True, text=True)
        if r.returncode: log("nft failed:", r.stderr.strip())
    log(f"BLOCK {ip_str(src)}")
    return True

# ---------------- MQTT ----------------------------------------------------------------------------------------------
inbox, t_alert, st = [], {}, dict(recs=0, alerts=0, blocks=0, swaps=0, fallback_recs=0, unclassified=0, held=0, verdicts=0)
def on_connect(c, u, f, rc, p=None):
    try: c.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)      # no 40 ms batching delay
    except (OSError, AttributeError): pass
    c.subscribe("ids/verdict")
    if a.input == "mqtt": c.subscribe("net/flows")
def on_message(c, u, msg):
    if msg.topic == "net/flows": inbox.append(msg.payload)
    else:
        d = json.loads(msg.payload); t0 = t_alert.pop(d["seq"], None); st["verdicts"] += 1
        if t0: log(f"VERDICT seq {d['seq']} {d['cat']} conf {d['conf']:.2f} round-trip {1000 * (time.time() - t0):.1f} ms")
try: cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ids-appliance")
except AttributeError: cli = mqtt.Client(client_id="ids-appliance")   # paho-mqtt 1.x, as in the PetaLinux image
if E("MQTT_USER"): cli.username_pw_set(E("MQTT_USER"), E("MQTT_PASS"))
cli.on_connect, cli.on_message = on_connect, on_message
cli.connect_async(a.broker, 1883, 30); cli.loop_start()
sock = None
if a.input == "udp":
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("0.0.0.0", a.port)); sock.setblocking(False)

# ---------------- rotation ------------------------------------------------------------------------------------------
active = rng.randrange(len(models)); swap_until = time.time() + backend.load(models[active]); held = []
def next_gap():
    if a.rotate == "off": return float("inf")
    return a.rotate_s if a.rotate == "fixed" else rng.expovariate(1.0 / a.rotate_s)
next_swap = time.time() + next_gap(); recent_alerts = []; last_swap = time.time(); t_status, t0 = 0.0, time.time()
def swap(reason):
    global active, swap_until, next_swap, last_swap, t_status
    t_status = 0.0                                                     # publish the new status right away
    if len(models) < 2: return
    active = rng.choice([i for i in range(len(models)) if i != active])
    swap_until = time.time() + backend.load(models[active]); st["swaps"] += 1; last_swap = time.time()
    next_swap = time.time() + next_gap()
    log(f"SWAP -> {models[active].meta.get('name', active)} ({reason}), blind window {a.swap_ms:.0f} ms, fallback={a.fallback}")

def handle(buf):
    n = len(buf) // RLEN
    if not n: return
    arr = np.frombuffer(buf[:n * RLEN], np.uint8).reshape(n, RLEN)
    hdr = [REC.unpack(bytes(r[:REC.size])) for r in arr]; X = arr[:, REC.size:]
    in_swap = time.time() < swap_until
    if in_swap and a.fallback == "open":
        st["unclassified"] += n; st["recs"] += n; return                # passed through unchecked (the worst case)
    if in_swap and a.fallback == "hold":
        held.append(bytes(buf)); st["held"] += n; return                # classified late, after the swap
    if in_swap: mg = fallback_model.margin(X); st["fallback_recs"] += n; who = 255
    else: mg = backend.margins(X); who = active
    st["recs"] += n
    for i in np.where(mg > 0)[0]:
        seq, src, ts = hdr[i]; st["alerts"] += 1; recent_alerts.append(time.time())
        if block(src): st["blocks"] += 1
        t_alert[seq] = time.time()
        cli.publish("ids/alert", struct.pack("<IIQB", seq, src, ts, who) + X[i].tobytes())
    if len(t_alert) > 5000:
        for k in list(t_alert)[:2500]: t_alert.pop(k, None)

log(f"idsd up: backend={backend.name} input={a.input} rotate={a.rotate}/{a.rotate_s}s pool={len(models)} N_IN={N_IN} "
    f"active={models[active].meta.get('name', active)}")
while True:
    got = False
    while inbox: handle(inbox.pop(0)); got = True
    if sock:
        try:
            while True: handle(sock.recv(65535)); got = True
        except BlockingIOError: pass
    now = time.time()
    if held and now >= swap_until:
        for b in held: handle(b)
        held.clear()
    if now >= next_swap: swap("timer")
    if a.rotate == "event":
        recent_alerts[:] = [t for t in recent_alerts if now - t < a.event_s]
        if len(recent_alerts) >= a.event_n and now - last_swap > max(2.0, 3 * a.swap_ms / 1000):
            recent_alerts.clear(); swap("probing suspected")
    if now - t_status > 2:
        t_status = now
        cli.publish("ids/status", json.dumps({**st, "member": models[active].meta.get("name", str(active)),
                    "version": manifest["version"], "pool": len(models), "in_swap": now < swap_until, "backend": backend.name,
                    "rotate": a.rotate, "pack": pack_dir, "uptime": round(now - t0, 1)}))
    if not got: time.sleep(0.002)
