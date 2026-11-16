# ml/e4_fingerprint.py — E4a: can the attacker tell WHICH model is active just from blocked/allowed answers?  Owner: P4
# If yes, rotation alone is weak: the attacker fingerprints the active model with a few probes, then replays an
# evasion it found earlier for that model (attacker A4, 'fingerprint then attack').
# usage: python ml/e4_fingerprint.py [--n 3000]      -> results/e4_fingerprint.csv
import argparse, csv, itertools, os
import numpy as np
from attacks import load_models, load_test, sample_knobs
from features import encode, apply_knobs
ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=3000); ap.add_argument("--budget", type=int, default=200)
ap.add_argument("--models", default="models"); ap.add_argument("--data", default="data/unsw_prep.npz"); a = ap.parse_args()
pool = load_models(os.path.join(a.models, "pool")); names = list(pool); P = len(names)
R, C, sc, _ = load_test(a.models, a.data, a.n, seed=2); rng = np.random.default_rng(0)
# candidate probes: things the attacker can really send = attack records with random knob settings + ordinary benign traffic
Rb, Cb, _, _ = load_test(a.models, a.data, a.n, seed=3, label=0)
Xc = np.vstack([encode(apply_knobs(R, sample_knobs(rng, len(R))), C, sc), encode(Rb, Cb, sc)])
D = np.array([m.predict(Xc) for m in pool.values()])                 # (P, candidates): the answer each member gives
useful = np.where((D.sum(0) > 0) & (D.sum(0) < P))[0]                # members disagree on these
print(f"{len(useful)} of {D.shape[1]} candidate probes split the pool ({len(useful) / D.shape[1]:.1%})")
pairs = list(itertools.combinations(range(P), 2)); chosen, undist = [], set(pairs)
while undist and len(useful):                                        # greedy: each probe separates as many pairs as possible
    gain = [sum(D[i, c] != D[j, c] for i, j in undist) for c in useful]
    if max(gain) == 0: break
    c = useful[int(np.argmax(gain))]; chosen.append(int(c)); undist = {(i, j) for i, j in undist if D[i, c] == D[j, c]}
sig = {names[i]: "".join("1" if D[i, c] else "0" for c in chosen) for i in range(P)}
print("probes needed:", len(chosen), "| signatures:", sig, "| pairs still identical:", len(undist))
# cost of attacker A4: find one evasion per member (label-only random search), then: probe -> look up -> send
q_first = []
for m in pool.values():
    det = m.predict(encode(R, C, sc)); Rr, Cr = R[det][:500], C[det][:500]; first = np.full(len(Rr), a.budget + 1)
    for q in range(a.budget):
        e = ~m.predict(encode(apply_knobs(Rr, sample_knobs(rng, len(Rr))), Cr, sc)); first = np.where(e & (first > a.budget), q + 1, first)
    q_first.append(float(np.median(first)))
rows = [{"pool_size": P, "probes_to_identify_member": len(chosen), "unidentifiable_pairs": len(undist),
         "probe_share_that_splits_pool": round(len(useful) / D.shape[1], 3),
         "median_queries_to_evade_one_member": float(np.mean(q_first)),
         "A4_setup_queries_total": float(np.sum(q_first)), "A4_queries_per_attack_afterwards": len(chosen) + 1}]
os.makedirs("results", exist_ok=True)
with open("results/e4_fingerprint.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(rows[0]); print("saved results/e4_fingerprint.csv")
