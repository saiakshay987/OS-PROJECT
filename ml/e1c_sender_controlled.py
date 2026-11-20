# ml/e1c_sender_controlled.py — E1c: transfer when the attacker edits only what a SENDER can set (and, in tier B, what it
# can influence within bounds). Classes: published UNSW-NB15 definitions + relations checked in our data; ALL ranges are
# our assumptions. k = number of sender actions (edited features); derived features are recomputed and do not count.
# Greedy coordinate search on the source model's score (deterministic). Baseline: k random actions with random grid
# values (seeds 1..trials). Same models, records (load_test, seed 0) and cell definition as E1.            Owner: P3
# usage: python ml/e1c_sender_controlled.py [--n 2000] [--trials 5]   -> results/e1c_*.csv
import argparse, csv, os
import numpy as np
from scipy.stats import beta
from attacks import load_models, load_test, set_scales
from features import encode, IDX, N_NUM
from sender_actions import SenderActions, TIERS, fast_margin
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=2000); ap.add_argument("--trials", type=int, default=5)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz"); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); targets = {**pool, **load_models(os.path.join(a.models, "baseline"))}
sources = {**targets, **load_models(os.path.join(a.models, "attacker"))}; P6 = list(pool)
R0, C, sc, z = load_test(a.models, a.data, a.n); X0 = encode(R0, C, sc); N = len(R0)
set_scales(list(sources.values()), X0)
det = {n: m.predict(X0) for n, m in targets.items()}; alld = np.all([det[n] for n in pool], axis=0)
sa = SenderActions(R0, C, sc, z)                                        # threat model: ml/sender_actions.py
ACT, IDENT, OK_STTL, LUT, ST0, SWIN = sa.ACT, sa.IDENT, sa.OK_STTL, sa.LUT, sa.ST0, sa.SWIN
build, greedy, random_edit = sa.build, sa.greedy, sa.random_edit
for m in pool.values(): assert (np.rint(fast_margin(m, X0) * max(1.0, m._scale)) == m.margin(X0)).all(), "fast_margin != qmlp"

def score(P, k):
    R = build(P); X = encode(R, C, sc); assert (X[:, N_NUM:] == X0[:, N_NUM:]).all(), "one-hot bytes changed"
    ch = {n: R[:, IDX[n]] != R0[:, IDX[n]] for n in ACT}; nch = np.sum(list(ch.values()), axis=0)
    assert (nch <= k).all(), "budget exceeded"
    ev = {n: ~m.predict(X) for n, m in targets.items()}; pev = np.all([ev[n] for n in pool], axis=0)
    r = {n: float(ev[n][det[n]].mean()) for n in targets}
    r.update(pool_mean=float(np.mean([r[n] for n in pool])), evades_ALL_pool=float(pev[alld].mean()), actions_changed=float(nch.mean()))
    return r, int(pev[alld].sum()), {n: float(c.mean()) for n, c in ch.items()}

def upper95(x, n): return float(beta.ppf(0.95, x + 1, n - x)) if x < n else 1.0   # one-sided Clopper-Pearson

os.makedirs("results", exist_ok=True); summary, usage = [], []
with open("results/e1c_sttl_refused.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["sttl_value", "records_refused", "share_refused", "n"])
    for v, ok in OK_STTL.items(): w.writerow([int(v), int((~ok).sum()), round(float((~ok).mean()), 4), N])
own = np.array([LUT.get((ST0[i], R0[i, IDX["sttl"]], R0[i, IDX["dttl"]])) == R0[i, IDX["ct_state_ttl"]] for i in range(N)])
print(f"LUT reproduces the original ct_state_ttl for {own.mean():.4f} of the sample; sttl refusals: "
      f"{ {int(v): int((~ok).sum()) for v, ok in OK_STTL.items()} }; swin values {SWIN.tolist()}", flush=True)
for tier, S in TIERS.items():
    snaps = {sn: greedy(sm, S, len(S)) for sn, sm in sources.items()}; print("searched tier", tier, flush=True)
    for k in [1, 2, 3, "all"]:
        kk = len(S) if k == "all" else min(k, len(S)); rows = [{"crafted_on": "no_edits", **score(IDENT, 0)[0]}]; worst, wsrc = -1, ""
        for sn in sources:
            r, x, u = score(snaps[sn][kk], kk); rows.append({"crafted_on": sn, **r})
            usage.append({"tier": tier, "k": k, "crafted_on": sn, **{n: round(u[n], 4) for n in TIERS["B"]}})
            if x > worst: worst, wsrc = x, sn
        tr = [score(random_edit(S, kk, s), kk)[0] for s in range(1, a.trials + 1)]
        rows += [{"crafted_on": f"random_{nm}", **{c: float(f([t[c] for t in tr])) for c in tr[0]}} for nm, f in (("mean", np.mean), ("std", np.std))]
        assert all(v == 0 for c, v in rows[0].items() if c != "crafted_on"), "no_edits row is not all zero"
        with open(f"results/e1c_tier{tier}_k{k}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader()
            w.writerows([{c: (round(v, 4) if isinstance(v, float) else v) for c, v in r.items()} for r in rows])
        by = {r["crafted_on"]: r for r in rows}; M = np.array([[by[s][t] for t in P6] for s in P6])
        summary.append({"tier": tier, "k": k, "actions_available": len(S), "diag_mean": round(float(np.diag(M).mean()), 4),
                        "pool_offdiag_mean": round(float(M[~np.eye(6, dtype=bool)].mean()), 4),
                        "random_pool_mean": round(by["random_mean"]["pool_mean"], 4), "random_pool_std": round(by["random_std"]["pool_mean"], 4),
                        "s_fp32_pool_mean": round(by["s_fp32"]["pool_mean"], 4), "max_evades_ALL_pool_records": worst, "worst_source": wsrc,
                        "all6_detected": int(alld.sum()), "evades_ALL_pool_upper95": round(upper95(worst, int(alld.sum())), 4),
                        "mean_actions_changed_pool_src": round(float(np.mean([by[s]["actions_changed"] for s in P6])), 2)})
        print(summary[-1], flush=True)
for name, rows in (("summary", summary), ("feature_usage", usage)):
    with open(f"results/e1c_{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
