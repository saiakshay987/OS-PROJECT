# ml/e1_transfer.py — E1: do evasions found on one model work on another? (the diversity of the pool)   Owner: P3
# Cell [row, column] = of the attack records that the COLUMN model detects, the share that evade it when the
# adversarial version was crafted on the ROW model. Diagonal = attack on the model itself. Low off-diagonal = diverse.
# usage: python ml/e1_transfer.py [--n 2000] [--steps 80]       -> results/e1_transfer.csv (+ .png if matplotlib)
import argparse, csv, os
import numpy as np
from attacks import load_models, load_test, hill_climb, evades, set_scales
from features import encode
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=2000); ap.add_argument("--steps", type=int, default=80)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz"); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); base = load_models(os.path.join(a.models, "baseline"))
surr = load_models(os.path.join(a.models, "attacker"))
R, C, sc, _ = load_test(a.models, a.data, a.n); X0 = encode(R, C, sc)
targets = {**pool, **base}
set_scales(list(targets.values()) + list(surr.values()), X0)
quant = [m for n, m in surr.items() if n != "s_fp32"]
sources = {**{n: [m] for n, m in targets.items()}, **{n: [m] for n, m in surr.items()},
           "s_ensemble_q": quant, "s_ensemble_all": list(surr.values())}
detected = {n: m.predict(X0) for n, m in targets.items()}
os.makedirs("results", exist_ok=True); rows = []
for sn, sm in sources.items():
    K = hill_climb(sm, R, C, sc, a.steps)
    row = {"crafted_on": sn}
    for tn, tm in targets.items():
        d = detected[tn]; row[tn] = round(float(evades(tm, R, C, sc, K)[d].mean()), 3) if d.any() else float("nan")
    pool_ev = np.array([evades(m, R, C, sc, K) for m in pool.values()]); alld = np.all([detected[n] for n in pool], axis=0)
    row["pool_mean"] = round(float(np.mean([row[n] for n in pool])), 3)
    row["evades_ALL_pool"] = round(float(pool_ev.all(axis=0)[alld].mean()), 3) if alld.any() else float("nan")
    rows.append(row); print(row)
with open("results/e1_transfer.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
names = list(pool); M = np.array([[r[t] for t in names] for r in rows if r["crafted_on"] in names])
off = M[~np.eye(len(names), dtype=bool)]
print(f"\nwithin the pool: self-attack (diagonal) {np.diag(M).mean():.3f}, transfer (off-diagonal) {off.mean():.3f}")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    A = np.array([[r[t] for t in targets] for r in rows]); fig, ax = plt.subplots(figsize=(8, 6)); im = ax.imshow(A, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(range(len(targets)), list(targets), rotation=45, ha="right"); ax.set_yticks(range(len(rows)), [r["crafted_on"] for r in rows])
    ax.set_xlabel("tested on (target)"); ax.set_ylabel("crafted on (attacker's model)"); ax.set_title("E1: evasion transfer rate")
    for i in range(A.shape[0]):
        for j in range(A.shape[1]): ax.text(j, i, f"{A[i, j]:.2f}", ha="center", va="center", color="w" if A[i, j] < 0.6 else "k", fontsize=7)
    fig.colorbar(im); fig.tight_layout(); fig.savefig("results/e1_transfer.png", dpi=150); print("saved results/e1_transfer.png")
except ImportError:
    pass
