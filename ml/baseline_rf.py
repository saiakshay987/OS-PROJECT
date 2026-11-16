# ml/baseline_rf.py — a standard non-neural baseline (Random Forest) on the same records, at the same false-positive rate.
# usage: pip install scikit-learn ; python ml/baseline_rf.py [--fpr 0.05]     appends a row to models/metrics.csv   Owner: P3
import argparse, csv, os, sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import encode, load_scaler
ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/unsw_prep.npz"); ap.add_argument("--out", default="models")
ap.add_argument("--fpr", type=float, default=0.05); a = ap.parse_args()
z = np.load(a.data); sc = load_scaler(os.path.join(a.out, "scaler.json"))
Xd, yd = encode(z["R_def"], z["C_def"], sc), z["y_def"].astype(int); Xt, yt = encode(z["R_test"], z["C_test"], sc), z["y_test"].astype(int)
nv = len(Xd) // 10; rf = RandomForestClassifier(200, n_jobs=-1, random_state=0).fit(Xd[:-nv], yd[:-nv])
pv = rf.predict_proba(Xd[-nv:])[:, 1]; thr = np.quantile(pv[yd[-nv:] == 0], 1 - a.fpr)       # same FPR rule as the pool
p = rf.predict_proba(Xt)[:, 1] > thr; tp = (p & (yt == 1)).sum(); fp = (p & (yt == 0)).sum(); fn = (~p & (yt == 1)).sum(); tn = (~p & (yt == 0)).sum()
pr, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
row = {"model": "random_forest", "group": "baseline", "acc": round(float((tp + tn) / len(yt)), 4), "precision": round(float(pr), 4), "recall": round(float(rc), 4),
       "f1": round(float(2 * pr * rc / max(1e-9, pr + rc)), 4), "fpr": round(float(fp / max(1, fp + tn)), 4), "float_int_agreement": "", "thr": round(float(thr), 4)}
print(row)
with open(os.path.join(a.out, "metrics.csv"), "a", newline="") as f: csv.DictWriter(f, fieldnames=list(row)).writerow(row)
