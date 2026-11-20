# ml/e1c_sender_controlled.py — E1c: transfer when the attacker edits only what a SENDER can set (and, in tier B, what it
# can influence within bounds). Classes: published UNSW-NB15 definitions + relations checked in our data; ALL ranges are
# our assumptions. k = number of sender actions (edited features); derived features are recomputed and do not count.
# Greedy coordinate search on the source model's score (deterministic). Baseline: k random actions with random grid
# values (seeds 1..trials). Same models, records (load_test, seed 0) and cell definition as E1.            Owner: P3
# usage: python ml/e1c_sender_controlled.py [--n 2000] [--trials 5]   -> results/e1c_*.csv
import argparse, csv, os
from collections import Counter, defaultdict
import numpy as np
from scipy.stats import beta
from attacks import load_models, load_test, set_scales
from features import encode, apply_knobs, IDX, N_NUM, CATS, KNOBS
from qmlp import QMLP
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=2000); ap.add_argument("--trials", type=int, default=5)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz"); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); targets = {**pool, **load_models(os.path.join(a.models, "baseline"))}
sources = {**targets, **load_models(os.path.join(a.models, "attacker"))}; P6 = list(pool)
R0, C, sc, z = load_test(a.models, a.data, a.n); X0 = encode(R0, C, sc); N = len(R0)
set_scales(list(sources.values()), X0)
det = {n: m.predict(X0) for n, m in targets.items()}; alld = np.all([det[n] for n in pool], axis=0)
po = len(CATS["proto"]) + 1; so = po + len(CATS["service"]) + 1
state = lambda Cm: Cm[:, so:so + len(CATS["state"]) + 1].argmax(1)
TCP, HTTP, ALL, ST0 = C[:, CATS["proto"].index("tcp")] > 0, C[:, po + CATS["service"].index("http")] > 0, np.ones(N, bool), state(C)
Rd, Cd, yd = z["R_def"], z["C_def"], z["y_def"]                        # lookups use the DEFENDER split only
tab = defaultdict(Counter)
for k in zip(state(Cd), Rd[:, IDX["sttl"]], Rd[:, IDX["dttl"]], Rd[:, IDX["ct_state_ttl"]]): tab[k[:3]][k[3]] += 1
LUT = {k: c.most_common(1)[0][0] for k, c in tab.items()}              # (state, sttl, dttl) -> majority ct_state_ttl
w = Rd[(yd == 0) & (Cd[:, 0] > 0), IDX["swin"]]; v, c = np.unique(w, return_counts=True); SWIN = v[c >= 0.01 * len(w)]
CT = ["ct_srv_src", "ct_dst_ltm", "ct_src_dport_ltm", "ct_dst_sport_ltm", "ct_dst_src_ltm", "ct_src_ltm", "ct_srv_dst"]
CTMAX = {n: Rd[:, IDX[n]].max() for n in CT}
lg = lambda lo, hi: np.exp(np.linspace(np.log(lo), np.log(hi), 7))
ACT = {n: (lg(lo, hi), ALL) for n, lo, hi in KNOBS}                    # E1's five knobs, same ranges
ACT.update(sttl=(np.array([31.0, 62.0, 64.0, 254.0]), ALL), swin=(SWIN, TCP), ackdat=(lg(1, 4), TCP),
           trans_depth=(np.arange(4.0), HTTP), dbytes=(lg(0.1, 10), ALL), dpkts=(lg(0.1, 10), ALL),
           response_body_len=(lg(0.1, 10), ALL), **{n: (np.array([0, 1, 2, 3, 5, 7, 10.0]), ALL) for n in CT})
OK_STTL = {v: np.array([(ST0[i], v, R0[i, IDX["dttl"]]) in LUT for i in range(N)]) for v in ACT["sttl"][0]}
IDENT = {n: (np.full(N, np.nan) if n in ("sttl", "swin") else np.zeros(N) if n == "trans_depth" or n in CT else np.ones(N)) for n in ACT}
TA = [n for n, _, _ in KNOBS] + ["sttl", "swin", "ackdat", "trans_depth"]
TIERS = {"A": TA, "A_sttl_only": ["sttl"], "A_no_sttl": [n for n in TA if n != "sttl"], "B": TA + ["dbytes", "dpkts", "response_body_len"] + CT}

def build(P):                                                           # all edits, then recompute every derived feature
    R = apply_knobs(R0, np.stack([P[n] for n, _, _ in KNOBS], 1))       # dur/sbytes/spkts/sinpkt/sjit + rate/sload/smean/dload
    pk_old = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]; db, dp = P["dbytes"], P["dpkts"]
    R[:, IDX["dbytes"]] = np.rint(R[:, IDX["dbytes"]] * db)
    R[:, IDX["dpkts"]] = np.where(R0[:, IDX["dpkts"]] > 0, np.maximum(1, np.rint(R[:, IDX["dpkts"]] * dp)), 0)
    pk_new = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]
    R[:, IDX["rate"]] *= np.where(pk_old > 0, pk_new / np.maximum(pk_old, 1), 1.0)
    R[:, IDX["dmean"]] = np.rint(R[:, IDX["dmean"]] * db / dp); R[:, IDX["dload"]] *= db
    R[:, IDX["response_body_len"]] = np.rint(R[:, IDX["response_body_len"]] * P["response_body_len"])
    R[:, IDX["ackdat"]] *= P["ackdat"]; R[:, IDX["tcprtt"]] = R[:, IDX["synack"]] + R[:, IDX["ackdat"]]
    R[:, IDX["trans_depth"]] += P["trans_depth"]
    for n in CT: R[:, IDX[n]] = np.minimum(R0[:, IDX[n]] + P[n], np.maximum(CTMAX[n], R0[:, IDX[n]]))
    s = ~np.isnan(P["swin"]); R[s, IDX["swin"]] = P["swin"][s]
    s = np.where(~np.isnan(P["sttl"]))[0]; R[s, IDX["sttl"]] = P["sttl"][s]
    R[s, IDX["ct_state_ttl"]] = [LUT[(ST0[i], P["sttl"][i], R0[i, IDX["dttl"]])] for i in s]
    return R

def allowed(n, v): return OK_STTL[v] if n == "sttl" else ACT[n][1]

def fast_margin(m, X):          # search only: float64 copy of the qmlp.py integer arithmetic (exact, values < 2^53)
    if not isinstance(m, QMLP): return m.margin(X) / max(1.0, m._scale)
    x = X.astype(np.float64)
    for ly in m.layers:
        acc = x @ ly["W"].T.astype(np.float64) + ly["b"]
        if ly["L"] is None: return (acc[:, 0] - m.thr) / max(1.0, m._scale)
        x = np.clip(np.floor((acc * ly["M"] + 2.0 ** (ly["SH"] - 1)) / 2.0 ** ly["SH"]), 0, ly["L"])

R_id = build(IDENT)                                                     # sanity: no edit must reproduce the record exactly
assert np.allclose(R_id, R0, rtol=1e-9, atol=1e-5) and (encode(R_id, C, sc) == X0).all(), "recomputation changes an unedited record"
for m in pool.values(): assert (np.rint(fast_margin(m, X0) * max(1.0, m._scale)) == m.margin(X0)).all(), "fast_margin != qmlp"

def greedy(m, S, rounds):                                               # one action per record per round; snapshot every round
    P = {n: v.copy() for n, v in IDENT.items()}; best = fast_margin(m, X0); snaps = {}
    for rnd in range(1, rounds + 1):
        bs, ba, bv = best.copy(), np.full(N, -1), np.zeros(N)
        for ai, n in enumerate(S):
            old = P[n].copy()
            for v in ACT[n][0]:
                ok = allowed(n, v); P[n] = np.where(ok, v, old); s = fast_margin(m, encode(build(P), C, sc)); b = ok & (s < bs)
                bs[b], ba[b], bv[b] = s[b], ai, v
            P[n] = old
        for ai, n in enumerate(S): r = ba == ai; P[n][r] = bv[r]
        best = bs; snaps[rnd] = {n: v.copy() for n, v in P.items()}
    return snaps

def random_edit(S, k, seed):
    rng = np.random.default_rng(seed); P = {n: v.copy() for n, v in IDENT.items()}
    pick = np.argsort(rng.random((N, len(S))), axis=1)[:, :min(k, len(S))]
    for ai, n in enumerate(S):
        r = (pick == ai).any(1); v = rng.choice(ACT[n][0], N); ok = r
        for g in ACT[n][0]: ok = ok & ~((v == g) & ~allowed(n, g))       # refused (not applicable / unknown sttl key): no edit
        P[n] = np.where(ok, v, P[n])
    return P

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
