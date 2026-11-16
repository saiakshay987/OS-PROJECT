# app/laptop/replay.py — plays test-set records at the appliance like a flow exporter would, then scores the alerts.
# usage: python app/laptop/replay.py --broker 127.0.0.1 [--n 5000] [--rate 500] [--transport mqtt|udp --host IP]   Owner: P3
import argparse, socket, struct, sys, time
import numpy as np, paho.mqtt.client as mqtt
ap = argparse.ArgumentParser()
ap.add_argument("--broker", default="127.0.0.1"); ap.add_argument("--transport", default="mqtt", choices=["mqtt", "udp"])
ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=5555)
ap.add_argument("--data", default="models/test_encoded.npz"); ap.add_argument("--n", type=int, default=5000)
ap.add_argument("--rate", type=float, default=500); ap.add_argument("--attackers", type=int, default=8)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--csv", default=None); ap.add_argument("--label", default="")     # append one result row to a CSV
a = ap.parse_args()
z = np.load(a.data); rng = np.random.default_rng(a.seed)
idx = rng.choice(len(z["X"]), min(a.n, len(z["X"])), replace=False); X, y = z["X"][idx], z["y"][idx]
ip = lambda s: struct.unpack(">I", socket.inet_aton(s))[0]
src = np.where(y == 1, [ip(f"10.0.9.{1 + i % a.attackers}") for i in range(len(y))], [ip(f"10.0.0.{1 + i % 50}") for i in range(len(y))])
alerts, lat, status = set(), [], {}
def on_message(c, u, m):
    if m.topic == "ids/alert":
        seq, _, ts, _ = struct.unpack("<IIQB", m.payload[:17]); alerts.add(seq); lat.append(time.time() * 1000 - ts)
    else:
        import json; status.update(json.loads(m.payload))
cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="replay")
cli.on_message = on_message; cli.connect(a.broker, 1883, 30)
cli.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
cli.subscribe([("ids/alert", 0), ("ids/status", 0)]); cli.loop_start()
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if a.transport == "udp" else None
time.sleep(0.5); batch = max(1, int(a.rate * 0.05)); t0 = time.time()
for i in range(0, len(X), batch):
    buf = b"".join(struct.pack("<IIQ", int(idx[j]), int(src[j]), int(time.time() * 1000)) + X[j].tobytes()
                   for j in range(i, min(i + batch, len(X))))
    if udp: udp.sendto(buf, (a.host, a.port))
    else: cli.publish("net/flows", buf)
    time.sleep(max(0, t0 + (i + batch) / a.rate - time.time()))
dt = time.time() - t0; time.sleep(3)
pred = np.array([int(s) in alerts for s in idx]); tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum())
fn = int((~pred & (y == 1)).sum()); tn = int((~pred & (y == 0)).sum())
print(f"sent {len(X)} records in {dt:.1f} s ({len(X) / dt:.0f}/s), {int(y.sum())} attacks")
print(f"alerts {len(alerts)}  TP {tp} FP {fp} FN {fn} TN {tn}  recall {tp / max(1, tp + fn):.3f}  FPR {fp / max(1, fp + tn):.3f}")
if lat: print(f"record sent -> alert seen: median {np.median(lat):.1f} ms, p95 {np.percentile(lat, 95):.1f} ms (same-clock machines only)")
print("appliance status:", status)
if a.csv:
    import csv, os
    row = {"label": a.label, "sent": len(X), "rate": round(len(X) / dt), "attacks": int(y.sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
           "recall": round(tp / max(1, tp + fn), 4), "fpr": round(fp / max(1, fp + tn), 4),
           "alert_ms_p50": round(float(np.median(lat)), 1) if lat else "", "alert_ms_p95": round(float(np.percentile(lat, 95)), 1) if lat else "",
           **{k: status.get(k, "") for k in ("swaps", "fallback_recs", "unclassified", "held", "recs")}}
    os.makedirs(os.path.dirname(a.csv) or ".", exist_ok=True); new = not os.path.exists(a.csv)
    with open(a.csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); new and w.writeheader(); w.writerow(row)
