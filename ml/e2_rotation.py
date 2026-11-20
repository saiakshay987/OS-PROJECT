# ml/e2_rotation.py — E2: does rotating the model help against an attacker who probes the detector?     Owner: P3
# Attacker A1/A2: label-only query attack. For each attack record it tries random knob settings, one query at a time,
#   and sees only 'blocked' or 'allowed'. The first 'allowed' is its evasion.
# Defender: 'static' = one model; 'rotate-K' = a different random pool member becomes active every K queries.
# We report: how often the attacker gets through within the budget, how many queries it needs, and — the key number —
# 'reuse': how often the SAME evasion still works when it is replayed later (after the model has changed).
# --attacker tierA / tierA_no_sttl: the E1c sender-controlled attacker (ml/sender_actions.py) instead of the five knobs;
#   each query = one random setting of every tier action; A0/A3 = greedy over all tier actions on the surrogate(s).
# usage: python ml/e2_rotation.py [--n 1000] [--budget 200] [--attacker knobs|tierA|tierA_no_sttl]
#        -> results/e2_rotation.csv (knobs) or results/e2_rotation_<attacker>.csv
import argparse, csv, os
import numpy as np
from attacks import load_models, load_test, sample_knobs, hill_climb, evades, set_scales
from features import encode, apply_knobs
from sender_actions import SenderActions, TIERS, fast_margin
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=1000); ap.add_argument("--budget", type=int, default=200)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz")
ap.add_argument("--attacker", default="knobs", choices=["knobs", "tierA", "tierA_no_sttl"]); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); base = load_models(os.path.join(a.models, "baseline"))
surr = load_models(os.path.join(a.models, "attacker")); names = list(pool); P = len(names)
R, C, sc, z = load_test(a.models, a.data, a.n, seed=1); X0 = encode(R, C, sc)
keep = np.all([m.predict(X0) for m in pool.values()] + [m.predict(X0) for m in base.values()], axis=0)   # detected by all
R, C = R[keep], C[keep]; N = len(R); rng = np.random.default_rng(0)
print(f"{N} attack records are detected by every model; attacking those")
TIER = None if a.attacker == "knobs" else TIERS[a.attacker[4:]]          # "tierA" -> TIERS["A"], "tierA_no_sttl" -> TIERS["A_no_sttl"]
sa = SenderActions(R, C, sc, z) if TIER else None; tag = f" [{a.attacker}]" if TIER else ""

# one pass: for every query, does the sampled record evade each model?   ev[q, model, record]
allm = {**pool, **base}; ev = np.zeros((a.budget, len(allm), N), bool)
for q in range(a.budget):
    if TIER: Xq = sa.encoded(sa.random_edit(TIER, len(TIER), rng=rng))
    else: K = sample_knobs(rng, N); Xq = encode(apply_knobs(R, K), C, sc)
    for i, m in enumerate(allm.values()): ev[q, i] = ~m.predict(Xq)
pool_ev = ev[:, :P]                                                  # (budget, P, N)

def run(active):                                                     # active[q] = index of the model answering query q
    hit = pool_ev[np.arange(a.budget), active]                       # (budget, N)
    ok = hit.any(axis=0); first = np.where(ok, hit.argmax(axis=0), a.budget)
    reuse = pool_ev[first[ok], :, np.where(ok)[0]].mean() if ok.any() else float("nan")     # works on a random member later
    every = pool_ev[first[ok], :, np.where(ok)[0]].all(axis=1).mean() if ok.any() else float("nan")
    return ok.mean(), (np.median(first[ok]) + 1 if ok.any() else float("nan")), reuse, every

rows = []
def add(defence, attacker, succ, q, reuse, every):
    rows.append({"defence": defence, "attacker": attacker + tag, "evasion_rate": round(float(succ), 3),
                 "median_queries": float(q), "reuse_after_swap": round(float(reuse), 3), "evades_all_members": round(float(every), 3)})
    print(rows[-1])
# static single pool members (average over which member is deployed) and the big baseline
st = [run(np.full(a.budget, i)) for i in range(P)]
add("static (one pool member, mean)", "A1 query", np.mean([s[0] for s in st]), float(np.nanmean([s[1] for s in st])), 1.0, np.nanmean([s[3] for s in st]))   # reuse = 1 by definition
for bi, bn in enumerate(base):
    h = ev[:, P + bi]; ok = h.any(axis=0)
    add(f"static ({bn})", "A1 query", ok.mean(), float(np.median(h.argmax(axis=0)[ok]) + 1) if ok.any() else float("nan"), 1.0, float("nan"))
for K in (1, 10, 50):
    act = np.repeat(rng.integers(0, P, a.budget // K + 1), K)[:a.budget]
    add(f"rotate every {K} queries", "A2 query (ignores rotation)", *run(act))
# A0: transfer from the attacker's own surrogates, no queries at all.  A3: pool-aware = ensemble of surrogates.
set_scales(list(surr.values()), X0)
for an, ms in (("A0 transfer (fp32 surrogate)", [surr["s_fp32"]]), ("A0 transfer (2-bit surrogate)", [surr["s_q2"]]),
               ("A3 pool-aware (surrogate ensemble)", list(surr.values()))):
    if TIER:
        E = type("Ens", (), {"_scale": 1.0, "margin": lambda self, X: np.max([fast_margin(m, X) for m in ms], axis=0)})()
        Xa = sa.encoded(sa.greedy(ms[0] if len(ms) == 1 else E, TIER, len(TIER))[len(TIER)])
        e = np.array([~m.predict(Xa) for m in pool.values()]); evb = lambda bm: ~bm.predict(Xa)
    else:
        K = hill_climb(ms, R, C, sc, 80); e = np.array([evades(m, R, C, sc, K) for m in pool.values()]); evb = lambda bm: evades(bm, R, C, sc, K)
    add("static (one pool member, mean)", an, e.mean(), 0, 1.0, e.all(axis=0).mean())
    add("rotating pool", an, e.mean(), 0, e.mean(), e.all(axis=0).mean())
    for bn, bm in base.items(): add(f"static ({bn})", an, evb(bm).mean(), 0, 1.0, float("nan"))
os.makedirs("results", exist_ok=True)
out = "results/e2_rotation.csv" if not TIER else f"results/e2_rotation_{a.attacker}.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("saved", out)
