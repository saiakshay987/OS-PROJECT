# app/laptop/stage2_server.py — receives alerts from the appliance, names the attack on the GPU, answers with a verdict.
# usage: python app/laptop/stage2_server.py --broker 127.0.0.1                                              Owner: P3
import argparse, json, socket, struct, time
import numpy as np, torch, torch.nn as nn, paho.mqtt.client as mqtt
ap = argparse.ArgumentParser(); ap.add_argument("--broker", default="127.0.0.1"); ap.add_argument("--model", default="models/stage2.pt")
a = ap.parse_args(); dev = "cuda" if torch.cuda.is_available() else "cpu"
ck = torch.load(a.model, map_location=dev); cats = ck["cats"]
net = nn.Sequential(nn.Linear(ck["n_in"], 512), nn.ReLU(), nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, len(cats))).to(dev)
net.load_state_dict(ck["state"]); net.eval(); n = {"alerts": 0, "gpu_ms": 0.0}
def on_message(c, u, m):
    if m.topic == "ids/status":
        s = json.loads(m.payload); print(f"[status] model {s['member']} swaps {s['swaps']} records {s['recs']} alerts {s['alerts']} blocks {s['blocks']}", flush=True); return
    seq, src, ts, who = struct.unpack("<IIQB", m.payload[:17]); x = np.frombuffer(m.payload[17:], np.uint8)
    t = time.perf_counter()
    with torch.no_grad(): p = torch.softmax(net(torch.tensor(x, dtype=torch.float32, device=dev)[None] / 255), 1)[0]
    k = int(p.argmax()); n["alerts"] += 1; n["gpu_ms"] += 1000 * (time.perf_counter() - t)
    c.publish("ids/verdict", json.dumps({"seq": seq, "cat": cats[k], "conf": float(p[k]), "ts": ts}))
    if n["alerts"] % 200 == 0: print(f"[stage 2] {n['alerts']} alerts, mean model time {n['gpu_ms'] / n['alerts']:.2f} ms on {dev}", flush=True)
    print(f"ALERT from {socket.inet_ntoa(struct.pack('>I', src))} by {'fallback' if who == 255 else 'model ' + str(who)} -> {cats[k]} ({float(p[k]):.2f})", flush=True)
cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="stage2")
cli.on_message = on_message; cli.connect(a.broker, 1883, 30)
cli.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
cli.subscribe([("ids/alert", 0), ("ids/status", 0)])
print(f"stage 2 ready on {dev}, classes: {cats}", flush=True); cli.loop_forever()
