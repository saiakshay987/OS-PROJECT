# bench/speed.py — how fast is each model on THIS machine? Run it on the laptop, inside QEMU and (later) on the board.
# usage: python bench/speed.py <label> [models/pool]     appends rows to results/speed.csv          Owner: P4
import csv, glob, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
sys.path.insert(0, "/opt/ids")
from qmlp import QMLP
label = sys.argv[1]; folder = sys.argv[2] if len(sys.argv) > 2 else "models/pool"; rows = []
for p in sorted(glob.glob(os.path.join(folder, "m*.npz"))):
    m = QMLP.load(p); n_in = m.layers[0]["W"].shape[1]; rng = np.random.default_rng(0)
    for batch in (1, 64, 1024):
        X = rng.integers(0, 256, (batch, n_in), dtype=np.uint8); reps = max(3, 2000 // batch); m.score(X)
        t = time.perf_counter()
        for _ in range(reps): m.score(X)
        us = 1e6 * (time.perf_counter() - t) / (reps * batch)
        rows.append({"where": label, "model": os.path.basename(p)[:-4], "batch": batch, "us_per_record": round(us, 2), "records_per_s": round(1e6 / us)})
        print(rows[-1])
os.makedirs("results", exist_ok=True); new = not os.path.exists("results/speed.csv")
with open("results/speed.csv", "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]));  new and w.writeheader(); w.writerows(rows)
