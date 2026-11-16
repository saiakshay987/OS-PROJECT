# ml/make_synth.py — a FAKE dataset with the UNSW-NB15 column layout, only for smoke-testing the code without the download.
# Never report numbers obtained from it.   python ml/make_synth.py data/synth 20000
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import NUM, CATS
out, n = sys.argv[1], int(sys.argv[2]); rng = np.random.default_rng(0); os.makedirs(out, exist_ok=True)
CAT_NAMES = ["Normal", "Generic", "Exploits", "Fuzzers", "DoS", "Reconnaissance", "Analysis", "Backdoor", "Shellcode", "Worms"]
def make(n):
    y = (rng.random(n) < 0.55).astype(int); cat = np.where(y == 0, 0, rng.integers(1, 10, n))
    d = {}
    for i, c in enumerate(NUM):
        base = rng.lognormal(1.0 + 0.15 * (i % 7), 1.0, n)
        shift = 1.0 + y * (0.30 * np.sin(i) + 0.15 * np.cos(cat * (i + 1)))       # attacks differ a little, per category
        d[c] = np.round(base * np.clip(shift, 0.2, None) + rng.normal(0, 0.3, n).clip(0), 6)
    d["dur"] = np.where(y == 1, d["dur"] * 0.4, d["dur"]); d["sload"] = np.where(y == 1, d["sload"] * 2.5, d["sload"])
    d["sttl"] = np.where((y == 1) & (rng.random(n) < 0.6), 254, rng.choice([31, 62], n))
    for col, vals in CATS.items():
        p = np.ones(len(vals)) / len(vals)
        d[col] = np.where((y == 1) & (rng.random(n) < 0.2), vals[1], rng.choice(vals, n, p=p))
    df = pd.DataFrame(d); df.insert(0, "id", np.arange(1, n + 1))
    df["attack_cat"] = [CAT_NAMES[c] for c in cat]; df["label"] = y
    return df
make(n).to_csv(os.path.join(out, "UNSW_NB15_training-set.csv"), index=False)
make(n // 2).to_csv(os.path.join(out, "UNSW_NB15_testing-set.csv"), index=False)
print("wrote FAKE data to", out)
