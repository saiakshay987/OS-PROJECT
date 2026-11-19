# ml/prepare.py — CSVs -> one prepared file with three disjoint splits.   Owner: P3
#   defender (60%): train the model pool      attacker (20%): data the attacker is assumed to have (for surrogates)
#   test (20%): never used for training; all reported numbers and all attacks use it
# usage: python ml/prepare.py <folder with the two UNSW-NB15 CSVs> [data/unsw_prep.npz]
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import split_raw, fit_scaler, save_scaler
src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else "data/unsw_prep.npz"
df = pd.concat([pd.read_csv(os.path.join(src, f), encoding="utf-8-sig", low_memory=False)
                for f in ("UNSW_NB15_training-set.csv", "UNSW_NB15_testing-set.csv")], ignore_index=True)
df.columns = [c.strip() for c in df.columns]
df = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
cats = sorted(df["attack_cat"].astype(str).str.strip().unique(), key=lambda c: (c != "Normal", c))
R, C = split_raw(df); y = df["label"].to_numpy(np.int8)
cat = df["attack_cat"].astype(str).str.strip().map({c: i for i, c in enumerate(cats)}).to_numpy(np.int8)
n = len(df); a, b = int(0.6 * n), int(0.8 * n)
scaler = fit_scaler(R[:a])                                   # fitted on the defender split only
os.makedirs(os.path.dirname(out) or ".", exist_ok=True); os.makedirs("models", exist_ok=True)
save_scaler(scaler, "models/scaler.json")
np.savez_compressed(out, cats=np.array(cats), **{f"{k}_{s}": v[i:j] for s, (i, j) in
                    {"def": (0, a), "atk": (a, b), "test": (b, n)}.items() for k, v in {"R": R, "C": C, "y": y, "cat": cat}.items()})
print(f"{n} records, {y.mean():.1%} attacks, classes {cats}\nsplits: defender {a}, attacker {b - a}, test {n - b} -> {out}")
