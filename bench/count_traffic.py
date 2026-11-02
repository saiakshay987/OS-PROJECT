# bench/count_traffic.py — run on the laptop during one measurement run; appends one CSV row
# usage: python bench/count_traffic.py <label> <seconds>    e.g.  fpga_vadon_silence 300
import json, os, sys, time, paho.mqtt.client as mqtt
label, secs = sys.argv[1], int(sys.argv[2])
n = {"msgs": 0, "bytes": 0, "cmds": 0, "cpu": [], "proc": []}

def on_msg(c, u, m):
    if m.topic == "pynq/features":
        n["msgs"] += 1; n["bytes"] += len(m.payload)
    elif m.topic == "pynq/status":
        s = json.loads(m.payload); n["cpu"].append(s["cpu_pct"]); n["proc"].append(s["proc_ms_avg"])
    elif m.topic == "laptop/command":
        n["cmds"] += 1

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="bench")
if os.getenv("MQTT_PASS"):
    c.username_pw_set("laptop", os.getenv("MQTT_PASS"))
c.on_message = on_msg
c.on_connect = lambda cl, *a: cl.subscribe([("pynq/#", 0), ("laptop/command", 0)])
c.connect(os.getenv("BROKER", "127.0.0.1"), 1883); c.loop_start(); time.sleep(secs); c.loop_stop()
avg = lambda v: round(sum(v) / len(v), 2) if v else "NA"
row = f"{label},{secs},{n['msgs']},{n['bytes']},{n['cmds']},{avg(n['cpu'])},{avg(n['proc'])}"
new = not os.path.exists("bench/track_e.csv")
with open("bench/track_e.csv", "a") as f:
    if new: f.write("label,seconds,feature_msgs,feature_bytes,commands,board_cpu_pct,proc_ms_per_window\n")
    f.write(row + "\n")
print(row)
