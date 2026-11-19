# ml/attacks.py — evasion attacks that only turn the knobs in common/features.py (so every adversarial record stays
# consistent), plus helpers shared by the experiments.                                                   Owner: P3
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import encode, apply_knobs, load_scaler, N_KNOBS, KLO, KHI
from qmlp import QMLP, FMLP

def load_models(folder):
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*.npz"))):
        n = os.path.basename(p)[:-4]
        if n == "canary": continue
        out[n] = (QMLP if "q0" in np.load(p).files else FMLP).load(p)
    return out

def load_test(models_dir="models", data="data/unsw_prep.npz", n_attacks=2000, seed=0, label=1):
    """Raw records from the test split with the given label (the attacker manipulates raw records, not encoded bytes)."""
    z = np.load(data); sc = load_scaler(os.path.join(models_dir, "scaler.json"))
    idx = np.where(z["y_test"] == label)[0]
    idx = np.random.default_rng(seed).choice(idx, min(n_attacks, len(idx)), replace=False)
    return z["R_test"][idx], z["C_test"][idx], sc, z

def sample_knobs(rng, n):
    return np.exp(rng.uniform(np.log(KLO), np.log(KHI), (n, N_KNOBS)))

def norm_margin(m, X):
    """Margin scaled per model so that different models can be combined (attack if > 0)."""
    return m.margin(X) / max(1.0, float(getattr(m, "_scale", 1.0)))

def set_scales(models, X):
    for m in models: m._scale = float(np.std(m.margin(X))) or 1.0

def hill_climb(models, R, C, sc, steps=80, seed=0, drop=False):
    """Score-based search on models the attacker OWNS (one model = white-box-style; several = ensemble/EOT).
    Minimises the worst (largest) margin over `models`. Returns the knob settings found."""
    rng = np.random.default_rng(seed); N = len(R); K = np.ones((N, N_KNOBS))
    f = lambda K_: np.max([norm_margin(m, encode(apply_knobs(R, K_), C, sc, drop)) for m in models], axis=0)
    best = f(K)
    for _ in range(steps):
        P = K.copy(); j = rng.integers(0, N_KNOBS, N)
        P[np.arange(N), j] = np.exp(rng.uniform(np.log(KLO[j]), np.log(KHI[j])))
        s = f(P); better = s < best; K[better] = P[better]; best[better] = s[better]
    return K

def evades(model, R, C, sc, K, drop=False):
    return ~model.predict(encode(apply_knobs(R, K), C, sc, drop))
