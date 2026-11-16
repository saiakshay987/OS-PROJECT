# app/laptop/attack_demo.py — live demo of the idea. An attacker probes the running appliance until one crafted
# record gets through, then keeps replaying exactly that record. With ROTATE=off it keeps working; with rotation
# it stops working when the model changes.  'Blocked or allowed' is read from the alert topic (stand-in for the
# attacker noticing that its connection was cut).                                                    Owner: P3
# usage: python app/laptop/attack_demo.py --broker 127.0.0.1 [--replay-s 60]
import argparse, json, os, socket, struct, sys, time
import numpy as np, paho.mqtt.client as mqtt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "common"))
from features import encode, apply_knobs, load_scaler, KLO, KHI, N_KNOBS
ap = argparse.ArgumentParser(); ap.add_argument("--broker", default="127.0.0.1"); ap.add_argument("--data", default="data/unsw_prep.npz")
ap.add_argument("--models", default="models"); ap.add_argument("--budget", type=int, default=300)
ap.add_argument("--replay-s", type=float, default=60); ap.add_argument("--seed", type=int, default=0); a = ap.parse_args()
z = np.load(a.data); sc = load_scaler(os.path.join(a.models, "scaler.json")); rng = np.random.default_rng(a.seed)
alerts, status = set(), {}
def on_message(c, u, m):
    if m.topic == "ids/alert": alerts.add(struct.unpack("<I", m.payload[:4])[0])
    else: status.update(json.loads(m.payload))
cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="attacker"); cli.on_message = on_message
cli.connect(a.broker, 1883, 30); cli.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
cli.subscribe([("ids/alert", 0), ("ids/status", 0)]); cli.loop_start(); time.sleep(2.5)
SRC = struct.unpack(">I", socket.inet_aton("10.0.9.99"))[0]; seq = [3_000_000_000]
def blocked(x):
    seq[0] += 1; cli.publish("net/flows", struct.pack("<IIQ", seq[0], SRC, int(time.time() * 1000)) + x.tobytes())
    time.sleep(0.08); return seq[0] in alerts
atk = np.where(z["y_test"] == 1)[0]; rng.shuffle(atk)
for i in atk:                                   # start from an attack record the detector does catch
    R, C = z["R_test"][i:i + 1], z["C_test"][i:i + 1]
    if blocked(encode(R, C, sc)[0]): break
print(f"attack record {i} is detected. Probing (active model: {status.get('member')}) ...")
found = None
for q in range(1, a.budget + 1):
    K = np.exp(rng.uniform(np.log(KLO), np.log(KHI), (1, N_KNOBS))); x = encode(apply_knobs(R, K), C, sc)[0]
    if not blocked(x): found = x; print(f"EVASION found after {q} probes; knobs (dur, bytes, pkts, spacing, jitter) = {np.round(K[0], 2)}"); break
if found is None: sys.exit(f"no evasion within {a.budget} probes for this record; try --seed 1")
ok = n = 0; t_end = time.time() + a.replay_s; last = None
while time.time() < t_end:
    b = blocked(found); n += 1; ok += not b; cur = status.get("member")
    if (b, cur) != last: print(f"t+{a.replay_s - (t_end - time.time()):5.1f}s  model {cur}: replay {'BLOCKED' if b else 'gets through'}"); last = (b, cur)
    time.sleep(0.9)
print(f"replayed {n} times: got through {ok} ({ok / n:.0%}), blocked {n - ok}")
