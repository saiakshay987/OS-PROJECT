# ml/e1_random_baseline.py — E1 control: how many detections are lost to RANDOM knob settings (no search at all)?
# Same records (n attacks from the test split, seed 0), same five knobs and ranges (log-uniform, attacks.sample_knobs),
# same scoring as e1_transfer.py. Each trial draws one random knob setting per record with its own fixed seed (1..trials).
# Rows: no_knobs (sanity, must be all 0), then mean / std / min / max over the trials.                     Owner: P3
# usage: python ml/e1_random_baseline.py [--n 2000] [--trials 5]       -> results/e1_random_baseline.csv
import argparse, csv, os
import numpy as np
from attacks import load_models, load_test, evades, sample_knobs
from features import encode, N_KNOBS
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=2000); ap.add_argument("--trials", type=int, default=5)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz"); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); targets = {**pool, **load_models(os.path.join(a.models, "baseline"))}
R, C, sc, _ = load_test(a.models, a.data, a.n); X0 = encode(R, C, sc)
detected = {n: m.predict(X0) for n, m in targets.items()}; alld = np.all([detected[n] for n in pool], axis=0)

def score(K):
    row = {n: float(evades(m, R, C, sc, K)[detected[n]].mean()) for n, m in targets.items()}
    row["pool_mean"] = float(np.mean([row[n] for n in pool]))
    row["evades_ALL_pool"] = float(np.all([evades(m, R, C, sc, K) for m in pool.values()], axis=0)[alld].mean())
    return row

rows = [{"row": "no_knobs", **score(np.ones((len(R), N_KNOBS)))}]
trials = [score(sample_knobs(np.random.default_rng(seed), len(R))) for seed in range(1, a.trials + 1)]
cols = list(trials[0])
for name, f in (("random_mean", np.mean), ("random_std", np.std), ("random_min", np.min), ("random_max", np.max)):
    rows.append({"row": name, **{c: f([t[c] for t in trials]) for c in cols}})
rows = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
os.makedirs("results", exist_ok=True)
with open("results/e1_random_baseline.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["row"] + cols); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
print(f"n={len(R)} records, trials={a.trials} (seeds 1..{a.trials}), detected by all six pool models: {int(alld.sum())}")
