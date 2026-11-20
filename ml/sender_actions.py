# ml/sender_actions.py — the sender-controlled threat model shared by E1c and E2 (moved unchanged out of
# e1c_sender_controlled.py). Feature classes: published UNSW-NB15 definitions + relations checked in our data; ALL ranges
# are our assumptions. Tier A = what a sender sets; tier B = A + bounded influence on the reply and the ct_* counts.
# Derived features are recomputed after every edit; ct_state_ttl after an sttl edit comes from a (state, sttl, dttl) lookup
# built from the DEFENDER split only.                                                                     Owner: P3
from collections import Counter, defaultdict
import numpy as np
from features import encode, apply_knobs, IDX, CATS, KNOBS
from qmlp import QMLP

CT = ["ct_srv_src", "ct_dst_ltm", "ct_src_dport_ltm", "ct_dst_sport_ltm", "ct_dst_src_ltm", "ct_src_ltm", "ct_srv_dst"]
TA = [n for n, _, _ in KNOBS] + ["sttl", "swin", "ackdat", "trans_depth"]
TIERS = {"A": TA, "A_sttl_only": ["sttl"], "A_no_sttl": [n for n in TA if n != "sttl"], "B": TA + ["dbytes", "dpkts", "response_body_len"] + CT}
lg = lambda lo, hi: np.exp(np.linspace(np.log(lo), np.log(hi), 7))

def fast_margin(m, X):          # search only: float64 copy of the qmlp.py integer arithmetic (exact, values < 2^53)
    if not isinstance(m, QMLP): return m.margin(X) / max(1.0, m._scale)
    x = X.astype(np.float64)
    for ly in m.layers:
        acc = x @ ly["W"].T.astype(np.float64) + ly["b"]
        if ly["L"] is None: return (acc[:, 0] - m.thr) / max(1.0, m._scale)
        x = np.clip(np.floor((acc * ly["M"] + 2.0 ** (ly["SH"] - 1)) / 2.0 ** ly["SH"]), 0, ly["L"])

class SenderActions:
    """Sender edits for one fixed set of raw records R0 with one-hots C (scaler sc); lookups from the defender split of z."""
    def __init__(self, R0, C, sc, z):
        self.R0, self.C, self.sc, self.N = R0, C, sc, len(R0); N = self.N; self.X0 = encode(R0, C, sc)
        po = len(CATS["proto"]) + 1; so = po + len(CATS["service"]) + 1
        state = lambda Cm: Cm[:, so:so + len(CATS["state"]) + 1].argmax(1)
        TCP, HTTP, ALL, self.ST0 = C[:, CATS["proto"].index("tcp")] > 0, C[:, po + CATS["service"].index("http")] > 0, np.ones(N, bool), state(C)
        Rd, Cd, yd = z["R_def"], z["C_def"], z["y_def"]                    # lookups use the DEFENDER split only
        tab = defaultdict(Counter)
        for k in zip(state(Cd), Rd[:, IDX["sttl"]], Rd[:, IDX["dttl"]], Rd[:, IDX["ct_state_ttl"]]): tab[k[:3]][k[3]] += 1
        self.LUT = {k: c.most_common(1)[0][0] for k, c in tab.items()}     # (state, sttl, dttl) -> majority ct_state_ttl
        w = Rd[(yd == 0) & (Cd[:, 0] > 0), IDX["swin"]]; v, c = np.unique(w, return_counts=True); self.SWIN = v[c >= 0.01 * len(w)]
        self.CTMAX = {n: Rd[:, IDX[n]].max() for n in CT}
        self.ACT = {n: (lg(lo, hi), ALL) for n, lo, hi in KNOBS}           # E1's five knobs, same ranges
        self.ACT.update(sttl=(np.array([31.0, 62.0, 64.0, 254.0]), ALL), swin=(self.SWIN, TCP), ackdat=(lg(1, 4), TCP),
                        trans_depth=(np.arange(4.0), HTTP), dbytes=(lg(0.1, 10), ALL), dpkts=(lg(0.1, 10), ALL),
                        response_body_len=(lg(0.1, 10), ALL), **{n: (np.array([0, 1, 2, 3, 5, 7, 10.0]), ALL) for n in CT})
        self.OK_STTL = {v: np.array([(self.ST0[i], v, R0[i, IDX["dttl"]]) in self.LUT for i in range(N)]) for v in self.ACT["sttl"][0]}
        self.IDENT = {n: (np.full(N, np.nan) if n in ("sttl", "swin") else np.zeros(N) if n == "trans_depth" or n in CT else np.ones(N)) for n in self.ACT}
        R_id = self.build(self.IDENT)                                       # sanity: no edit must reproduce the record exactly
        assert np.allclose(R_id, R0, rtol=1e-9, atol=1e-5) and (encode(R_id, C, sc) == self.X0).all(), "recomputation changes an unedited record"

    def build(self, P):                                                     # all edits, then recompute every derived feature
        R0 = self.R0; R = apply_knobs(R0, np.stack([P[n] for n, _, _ in KNOBS], 1))   # knobs + rate/sload/smean/dload
        pk_old = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]; db, dp = P["dbytes"], P["dpkts"]
        R[:, IDX["dbytes"]] = np.rint(R[:, IDX["dbytes"]] * db)
        R[:, IDX["dpkts"]] = np.where(R0[:, IDX["dpkts"]] > 0, np.maximum(1, np.rint(R[:, IDX["dpkts"]] * dp)), 0)
        pk_new = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]
        R[:, IDX["rate"]] *= np.where(pk_old > 0, pk_new / np.maximum(pk_old, 1), 1.0)
        R[:, IDX["dmean"]] = np.rint(R[:, IDX["dmean"]] * db / dp); R[:, IDX["dload"]] *= db
        R[:, IDX["response_body_len"]] = np.rint(R[:, IDX["response_body_len"]] * P["response_body_len"])
        R[:, IDX["ackdat"]] *= P["ackdat"]; R[:, IDX["tcprtt"]] = R[:, IDX["synack"]] + R[:, IDX["ackdat"]]
        R[:, IDX["trans_depth"]] += P["trans_depth"]
        for n in CT: R[:, IDX[n]] = np.minimum(R0[:, IDX[n]] + P[n], np.maximum(self.CTMAX[n], R0[:, IDX[n]]))
        s = ~np.isnan(P["swin"]); R[s, IDX["swin"]] = P["swin"][s]
        s = np.where(~np.isnan(P["sttl"]))[0]; R[s, IDX["sttl"]] = P["sttl"][s]
        R[s, IDX["ct_state_ttl"]] = [self.LUT[(self.ST0[i], P["sttl"][i], R0[i, IDX["dttl"]])] for i in s]
        return R

    def encoded(self, P): return encode(self.build(P), self.C, self.sc)
    def allowed(self, n, v): return self.OK_STTL[v] if n == "sttl" else self.ACT[n][1]

    def greedy(self, m, S, rounds):                                         # one action per record per round; snapshot every round
        N = self.N; P = {n: v.copy() for n, v in self.IDENT.items()}; best = fast_margin(m, self.X0); snaps = {}
        for rnd in range(1, rounds + 1):
            bs, ba, bv = best.copy(), np.full(N, -1), np.zeros(N)
            for ai, n in enumerate(S):
                old = P[n].copy()
                for v in self.ACT[n][0]:
                    ok = self.allowed(n, v); P[n] = np.where(ok, v, old); s = fast_margin(m, self.encoded(P)); b = ok & (s < bs)
                    bs[b], ba[b], bv[b] = s[b], ai, v
                P[n] = old
            for ai, n in enumerate(S): r = ba == ai; P[n][r] = bv[r]
            best = bs; snaps[rnd] = {n: v.copy() for n, v in P.items()}
        return snaps

    def random_edit(self, S, k, seed=None, rng=None):                       # k random actions per record, random grid values
        N = self.N; rng = rng if rng is not None else np.random.default_rng(seed); P = {n: v.copy() for n, v in self.IDENT.items()}
        pick = np.argsort(rng.random((N, len(S))), axis=1)[:, :min(k, len(S))]
        for ai, n in enumerate(S):
            r = (pick == ai).any(1); v = rng.choice(self.ACT[n][0], N); ok = r
            for g in self.ACT[n][0]: ok = ok & ~((v == g) & ~self.allowed(n, g))   # refused (not applicable / unknown sttl key): no edit
            P[n] = np.where(ok, v, P[n])
        return P
