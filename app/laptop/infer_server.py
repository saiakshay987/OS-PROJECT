# app/laptop/infer_server.py — core logic (add argparse, logging and a CSV log yourself)
import json, os, struct, sys, time, numpy as np, onnxruntime as ort, paho.mqtt.client as mqtt
from actions import do_action
LABELS = ["up","down","left","right","stop","go","yes","no","on","off","_silence_","_unknown_"]
HDR = struct.Struct("<QIHH")                       # ts_ms, window number, speech frames, flags
sess = ort.InferenceSession("ml/kws.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
st = {"last_seq": None, "history": [], "last_fire": 0.0, "inferences": 0}

def softmax(z):
    e = np.exp(z - z.max()); return e / e.sum()

def on_features(cli, msg):
    ts, seq, n_speech, flags = HDR.unpack_from(msg.payload)
    f = np.frombuffer(msg.payload, np.float32, offset=HDR.size).reshape(49, 40)
    if st["last_seq"] is None or seq != st["last_seq"] + 1:
        st["history"].clear()                      # gap in window numbers = the gate closed in between
    st["last_seq"] = seq
    f = f - f.mean(axis=0, keepdims=True)          # CMVN
    p = softmax(sess.run(None, {"x": f[None, None]})[0][0]); st["inferences"] += 1
    k = int(p.argmax()); word, conf = LABELS[k], float(p[k])
    h = st["history"]; h.append(word); del h[:-2]
    # fire if the same word wins 2 windows in a row, is confident, and we're not in cooldown
    if word[0] != "_" and conf > 0.80 and h == [word, word] and time.time() - st["last_fire"] > 1.0:
        do_action(word); st["last_fire"] = time.time()
        cli.publish("laptop/command", json.dumps({"word": word, "conf": conf, "ts": ts}))

def on_status(msg):
    s = json.loads(msg.payload)
    print(f"[board] {s['backend']} vad={s['vad']} floor={s['noise_floor_db']} dB "
          f"sent {s['published']}/{s['windows']} windows, cpu {s['cpu_pct']}% "
          f"| laptop inferences so far: {st['inferences']}", flush=True)

def on_message(cli, userdata, msg):
    on_features(cli, msg) if msg.topic == "pynq/features" else on_status(msg)

cli = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="laptop")
if os.getenv("MQTT_PASS"):                         # after P4's hardening
    cli.username_pw_set("laptop", os.getenv("MQTT_PASS"))
cli.on_message = on_message
cli.on_connect = lambda c, *a: c.subscribe([("pynq/features", 0), ("pynq/status", 0)])
cli.connect("127.0.0.1", 1883); cli.loop_forever()
