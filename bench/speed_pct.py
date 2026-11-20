# bench/speed_pct.py: like speed.py but reports mean, median and p95 per record. Run inside the guest: python3 speed_pct.py <label> /opt/ids/pool-factory. Owner: P2
import csv, glob, os, sys, time
import numpy as np
sys.path.insert(0, "/opt/ids")
from qmlp import QMLP
label = sys.argv[1]; folder = sys.argv[2]
REPS = {1: 1000, 64: 300, 1024: 50}
rows = []
for p in sorted(glob.glob(os.path.join(folder, "m*.npz"))):
    m = QMLP.load(p); n_in = m.layers[0]["W"].shape[1]; rng = np.random.default_rng(0)
    for batch in (1, 64, 1024):
        X = rng.integers(0, 256, (batch, n_in), dtype=np.uint8); m.score(X)
        ts = []
        for _ in range(REPS[batch]):
            t = time.perf_counter(); m.score(X); ts.append((time.perf_counter() - t) * 1e6 / batch)
        a = np.array(ts)
        rows.append({"where": label, "model": os.path.basename(p)[:-4], "batch": batch, "calls": len(a), "mean_us": round(float(a.mean()), 2), "median_us": round(float(np.median(a)), 2), "p95_us": round(float(np.percentile(a, 95)), 2)})
        print(rows[-1])
os.makedirs("results", exist_ok=True)
with open("results/speed_pct.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
