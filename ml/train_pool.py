# ml/train_pool.py — train the defender's model pool, the big baseline and the attacker's surrogates; export everything.
# usage: python ml/train_pool.py [--data data/unsw_prep.npz] [--epochs 15] [--fpr 0.05] [--drop-shortcuts]     Owner: P3
import argparse, csv, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import encode, load_scaler
import qat
ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/unsw_prep.npz"); ap.add_argument("--out", default="models")
ap.add_argument("--epochs", type=int, default=15); ap.add_argument("--fpr", type=float, default=0.05)
ap.add_argument("--drop-shortcuts", action="store_true")
a = ap.parse_args()

# The pool: members differ in seed, training subset, layer sizes and bit widths (w = weight bits, a = activation bits).
POOL = [dict(name="m0", hidden=[64, 64], wb=2, ab=2, seed=0, frac=1.0),
        dict(name="m1", hidden=[64, 64], wb=2, ab=2, seed=1, frac=0.7),
        dict(name="m2", hidden=[64, 32], wb=3, ab=3, seed=2, frac=1.0),
        dict(name="m3", hidden=[32, 32], wb=4, ab=4, seed=3, frac=0.7),
        dict(name="m4", hidden=[96, 48], wb=2, ab=4, seed=4, frac=0.7),
        dict(name="m5", hidden=[48, 48, 24], wb=4, ab=2, seed=5, frac=1.0)]
BASE = [dict(name="big_fp32", hidden=[256, 256], wb=0, ab=0, seed=10, frac=1.0)]           # one large full-precision model
SURR = [dict(name="s_fp32", hidden=[128, 128], wb=0, ab=0, seed=100, frac=1.0),            # attacker's surrogates,
        dict(name="s_q2", hidden=[64, 64], wb=2, ab=2, seed=101, frac=1.0),                # trained on the attacker split
        dict(name="s_q3", hidden=[64, 32], wb=3, ab=3, seed=102, frac=1.0),
        dict(name="s_q4", hidden=[48, 48], wb=4, ab=4, seed=103, frac=1.0)]

os.makedirs(a.out, exist_ok=True)
if not os.path.exists(os.path.join(a.out, "scaler.json")):                 # e.g. --out models_noshort: reuse the one from prepare.py
    import shutil; shutil.copy("models/scaler.json", os.path.join(a.out, "scaler.json"))
z = np.load(a.data); sc = load_scaler(os.path.join(a.out, "scaler.json"))
X = {s: encode(z[f"R_{s}"], z[f"C_{s}"], sc, a.drop_shortcuts) for s in ("def", "atk", "test")}
y = {s: z[f"y_{s}"].astype(int) for s in ("def", "atk", "test")}
nv = len(X["def"]) // 10                                    # last 10% of the defender split = validation (threshold only)
rows = []
for group, specs, split in (("pool", POOL, "def"), ("baseline", BASE, "def"), ("attacker", SURR, "atk")):
    os.makedirs(os.path.join(a.out, group), exist_ok=True)
    Xtr, ytr = (X[split][:-nv], y[split][:-nv]) if split == "def" else (X[split], y[split])
    for sp in specs:
        print(f"[{group}] {sp['name']}: hidden {sp['hidden']} w{sp['wb']} a{sp['ab']} seed {sp['seed']} on {qat.DEV}")
        net = qat.train(Xtr, ytr, sp["hidden"], sp["wb"], sp["ab"], sp["seed"], a.epochs, sp["frac"])
        m = qat.export(net, {**sp, "group": group, "drop_shortcuts": a.drop_shortcuts})
        Xv, yv = (X["def"][-nv:], y["def"][-nv:]) if split == "def" else (X["atk"][-nv:], y["atk"][-nv:])
        qat.calibrate(m, Xv, yv, a.fpr)
        agree = float(((qat.float_scores(net, X["test"]) > 0) == (m.score(X["test"]) > 0)).mean())
        r = {"model": sp["name"], "group": group, **{k: round(v, 4) for k, v in qat.metrics(m, X["test"], y["test"]).items()},
             "float_int_agreement": round(agree, 4), "thr": m.thr}
        rows.append(r); print("   ", r); m.save(os.path.join(a.out, group, sp["name"] + ".npz"))
# canary records: fixed inputs with known answers, used by the appliance to self-test a pack after loading it
rng = np.random.default_rng(0); Xv, yv = X["def"][-nv:], y["def"][-nv:]
ci = np.concatenate([rng.choice(np.where(yv == 0)[0], 32, replace=False), rng.choice(np.where(yv == 1)[0], 32, replace=False)])
np.savez(os.path.join(a.out, "pool", "canary.npz"), X=Xv[ci], y=yv[ci])
np.savez_compressed(os.path.join(a.out, "test_encoded.npz"), X=X["test"], y=y["test"], cat=z["cat_test"], cats=z["cats"])
with open(os.path.join(a.out, "metrics.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"saved models + metrics.csv to {a.out}/. Next: python common/modelpack.py sign {a.out}/pool keys/pool_priv.pem")
