# P3 notes (models, experiments, laptop side)

Every command that worked, every error and its fix, with dates. Every number with the commit and command that produced it.

## Environment (19-20 Nov 2026)
Windows 11, RTX 4050 Laptop GPU (driver 592.82). Venv `venv/` is conda-style: the interpreter is `venv\python.exe`
(not `venv\Scripts\python.exe`), Python 3.10.0. Installed: torch 2.6.0+cu124 (`cuda.is_available()` = True), numpy 2.2.6,
pandas 2.3.3, paho-mqtt 2.2.0, matplotlib 3.10.9, scikit-learn 1.7.2 (not in requirements.txt), pytest 8.4.2.

Errors and fixes:
- `git pull` on branch akshay: "no tracking information". Fix: `git pull origin main`.
- `.venv\Scripts\python.exe` not found: the venv is `venv\` and is conda-style, so use `venv\python.exe`.
- torch was missing: `venv\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124`, then
  `pip install -r requirements.txt scikit-learn`.
- `pytest -q` crashed with INTERNALERROR (`'NodeId' object has no attribute '_str_cache'`) on pytest 9.2.0.
  Fix: `pip install "pytest<9"` (now 8.4.2). requirements.txt does not pin pytest; teammates may hit the same crash.
- `pytest -q` on Windows: 3 passed, 2 failed. `test_install_is_versioned` fails with WinError 1314 (os.symlink needs a
  privilege on Windows). `test_generated_hls_code_matches_python` fails with WinError 2 (the test runs `./tb`, but g++
  on Windows writes `tb.exe`). Both fail identically on a clean export of main, so they are not caused by the model
  pack. Not run on Linux: needs a Linux run before the PR is merged.

## Data (20 Nov 2026)
Command: `python ml/prepare.py data/unsw`. Dataset: UNSW-NB15 training-set + testing-set CSVs (data/unsw/, not committed).
257,673 records, 63.9% attacks (higher than real traffic: the two CSVs are combined as-is).
Classes: Normal, Analysis, Backdoor, DoS, Exploits, Fuzzers, Generic, Reconnaissance, Shellcode, Worms.
Splits: defender 154,603 | attacker 51,535 | test 51,535 (intermediate file data/unsw_prep.npz, git-ignored).

## Model pack v1 (20 Nov 2026) - commit 50d7d8e, branch p3/model-pack-v1
Commands: `python ml/train_pool.py --epochs 20` (QAT_K2=2.0 default), then `python ml/baseline_rf.py`.
Metrics are the INTEGER models (arithmetic of common/qmlp.py) at the calibrated threshold, on the 51,535-record test split.
Threshold: 95th percentile of integer scores of benign records in the last 10% of the defender split (target fpr 0.05).
float_int_agreement: float model at its own calibrated threshold vs integer model at its threshold, on the test split.
"nonzero W" = fraction of non-zero weights; "dead" = hidden units whose output is 0 on every test record (per hidden layer);
"distinct" = number of distinct output scores.

| model | bits | acc | precision | recall | fpr | agreement | nonzero W | dead (per layer) | distinct |
|---|---|---|---|---|---|---|---|---|---|
| m0 | w2a2 | 0.9012 | 0.9718 | 0.8702 | 0.0443 | 0.9871 | 27.4% | 14% / 38% | 51 |
| m1 | w2a2 | 0.8907 | 0.9809 | 0.8449 | 0.0289 | 0.9916 | 25.2% | 19% / 44% | 40 |
| m2 | w3a3 | 0.9033 | 0.9767 | 0.8689 | 0.0364 | 0.9813 | 10.6% | 20% / 25% | 94 |
| m3 | w4a4 | 0.9051 | 0.9695 | 0.8787 | 0.0485 | 0.9978 | 53.8% | 6% / 12% | 376 |
| m4 | w2a4 | 0.9131 | 0.9700 | 0.8912 | 0.0483 | 0.9954 | 31.5% | 6% / 46% | 309 |
| m5 | w4a2 | 0.9020 | 0.9760 | 0.8674 | 0.0374 | 0.9894 | 47.2% | 17% / 0% / 4% | 154 |
| big_fp32 (float baseline) | - | 0.9320 | 0.9711 | 0.9207 | 0.0482 | 1.0 | - | - | - |
| random_forest | - | 0.9486 | 0.9714 | 0.9473 | 0.0490 | - | - | - | - |

Attacker surrogates (trained on the attacker split, not in the pool): s_fp32 0.9203 | s_q2 0.8929 | s_q3 0.8984 | s_q4 0.9040.
The pool models are about 2-4 points of accuracy below the big float model (m4 1.9, m1 4.1): that is the cost of 2-4 bit integer weights, not a bug.
m1 fpr is 0.029, below the 0.05 target: its integer threshold falls on a tie among 40 distinct scores, so it raises fewer
false alarms than targeted (conservative, not unsafe). Every K2 tried left one of m0/m1 near 0.03 (see sweep).

## Problem found and fixed: 2-bit models (20 Nov 2026)
First run (old scale = max|w|), same commands, QAT_K2 did not exist yet:

| model | acc | fpr | agreement | thr | distinct scores |
|---|---|---|---|---|---|
| m0 | 0.7911 | 0.0231 | 0.7787 | 0 | 9 |
| m1 | 0.7651 | 0.0008 | 1.0000 | 1 | 8 |
| m4 | 0.8614 | 0.0383 | 0.9175 | 3 | 73 |
| s_q2 | 0.7566 | 0.0091 | 0.9796 | 2 | 15 |

Cause (read-only diagnosis on the saved integer models): for 2-bit weights the scale was max|w|/1, so a few outlier weights
set the scale and about 99% of the weights rounded to 0 (m0 layer 0: 3861 of 3904 zero), with 86-88% dead hidden units.
The network had only 8-9 distinct output scores, so a quarter of benign records tied exactly at the threshold and fpr
could not be tuned to 0.05 (m0: fpr 0.269 at thr-1, 0.023 at thr).
The old agreement metric compared `float_logit > 0` with `int_score > 0` and ignored the calibrated threshold. For m0, 22.1%
of test records had integer score exactly 0 and the disagreement was 22.13%; this is consistent with the integer bias
rounding to 0 in coarse units, but NOT directly verified (the float network is not saved).
Fix (ml/ only, common/ untouched): `ml/qat.py` uses scale = K2 * mean|w| for 2-bit weights (env var QAT_K2, default 2.0);
`ml/train_pool.py` measures agreement at each model's calibrated threshold (new `qat.float_thr`).
The old and new agreement numbers are not comparable.

K2 sweep (same seeds, 20 epochs, written to a scratch folder, not to models/); each cell is acc / fpr / agreement:

| K2 | m0 | m1 | m4 | dead units in last hidden layer (m0 / m1) |
|---|---|---|---|---|
| 1.5 | 0.8935 / 0.0308 / 0.9981 | 0.8920 / 0.0435 / 0.9954 | 0.9027 / 0.0466 / 0.9947 | 23% / 27% |
| 2.0 (chosen) | 0.9012 / 0.0443 / 0.9871 | 0.8907 / 0.0289 / 0.9916 | 0.9131 / 0.0483 / 0.9954 | 38% / 44% |
| 3.0 | 0.8947 / 0.0317 / 1.0000 | 0.9012 / 0.0443 / 0.9984 | 0.9037 / 0.0398 / 0.9920 | 66% / 67% |

All three pass acc >= 0.80 and agreement >= 0.98 on every pool model. No clear winner: 2.0 has the best mean accuracy on the
2-bit pool models (0.902) and the best single model (m4 0.913), 1.5 has the fewest dead units, 3.0 wastes the most.
Each model was trained once; the accuracy differences (about 0.5 points) are within what one seed could change (not measured).
Kept K2 = 2.0 because it was the planned starting value.

## Signing and the key (20 Nov 2026)
`keys/pool_pub.pem` was committed by P4 (2aa68aa); the private key stays on P4's machine (keys_release/, git-ignored). The
`keygen` command overwrites existing keys without asking, so it was NOT run in this repo. models/pool in commit 50d7d8e is
UNSIGNED (m0.npz-m5.npz + canary.npz, no manifest). P4 signs it:
`python common/modelpack.py sign models/pool <path>/pool_priv.pem <version>` then
`python common/modelpack.py verify models/pool keys/pool_pub.pem` (expected: `OK: version <n>, 6 models`).
`sign` writes both `manifest.json` (version, SHA-256 of each model, canary answers) and `manifest.sig` (ECDSA P-256 over
manifest.json); both must be committed. Canary answers are computed at signing time, so the files must not be retrained
after signing.
Self-check with a throwaway key in a scratch folder (not the release key): sign + verify gave `OK: version 1, 6 models`;
verify with P4's real public key gave `REJECTED: signature check failed` (expected, pack is unsigned); one changed byte in
m3.npz gave `REJECTED: m3.npz: hash mismatch`.

## Not verified / open
- The pack has not been loaded by idsd.py in QEMU or on a board; only modelpack.py was run here.
- pytest on Linux not run (2 Windows-only failures above).
- Single seed per model; no repeat runs.
- The 6 models were trained on UNSW-NB15 flow records encoded to 61 bytes (common/features.py); no live-traffic evaluation.
- Tell the team to pin `pytest<9` in requirements.txt (not changed by P3).
