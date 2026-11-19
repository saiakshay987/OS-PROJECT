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

## Stage 2: E1 transfer experiment and the stage-2 model (20 Nov 2026) - branch p3/e1-e2-results
Code base: main at b3137f5 (model pack v1) plus the new ml/e1_random_baseline.py, committed together with these
results on branch p3/e1-e2-results. Models: the pack in models/ (QAT_K2=2.0). Dataset: UNSW-NB15 (data/unsw_prep.npz).

### Stage-2 classifier
Command: `python ml/train_stage2.py --epochs 20` -> models/stage2.pt (791,924 B, NOT in git: *.pt is ignored).
Float MLP 61-512-256-128-10 on the GPU, 10 categories (Normal + 9 attack types), class-weighted loss, seed 0.
Test accuracy (10 classes, 51,535 test records): 0.780 at epoch 20 (the saved model); best epoch 19 = 0.791.
The script saves the LAST epoch, not the best, and prints no per-class accuracy, so which categories it confuses is unknown.
app/laptop/stage2_server.py needs this file: it loads `--model` (default `models/stage2.pt`, relative to the folder
it is started from, so start it from the repo root) at startup and stops with an error if it is missing. Anyone who clones
the repo must run prepare.py + train_stage2.py (or get the file) first. Checked: torch 2.6 loads it with the default
`weights_only=True` (n_in 61, 10 classes).

### E1: how it works
Each cell [row R, column C] = of the attack records that model C detects, the share that evade C after the knobs were
tuned on model R. The attacker can only change the 5 knobs of common/features.py: dur x1-8, sbytes x1-4, spkts x1-3,
sinpkt x0.5-4, sjit x0.5-4 (score-based hill climb, ml/attacks.py, seed 0). n = 2,000 attack records from the test split
(seed 0); each column detects 1,676 (m1) to 1,779 (m4) of them, so 0.01 is about 17 records (1 standard error at 0.01 is
about 0.0024, estimated, not printed by the script).

Commands and files:
- `python ml/e1_transfer.py --n 2000 --steps 80` -> results/e1_transfer.csv, results/e1_transfer.png
- `python ml/e1_transfer.py --n 2000 --steps 400` -> results/e1_transfer_steps400.csv/.png
- `python ml/e1_transfer.py --n 2000 --steps 1000` -> results/e1_transfer_steps1000.csv/.png
  (e1_transfer.py always writes results/e1_transfer.csv/.png; the 400/1000 outputs were renamed and the 80-step files
  restored; the 80-step CSV hash was checked unchanged.) Run time: 400 steps 4 min, 1000 steps 8 min.
- `python ml/e1_random_baseline.py --n 2000 --trials 5` -> results/e1_random_baseline.csv (random knobs, same 5 knobs and
  ranges, log-uniform, no search, seeds 1-5; no_knobs sanity row is all 0 as required).

### E1 results (pool diagonal and pool_mean per row)
| model | diag 80 | diag 400 | diag 1000 | random mean +- std | pool_mean 80 | pool_mean 400 | pool_mean 1000 |
|---|---|---|---|---|---|---|---|
| m0 | 0.045 | 0.047 | 0.047 | 0.0134 +- 0.0009 | 0.013 | 0.014 | 0.014 |
| m1 | 0.023 | 0.025 | 0.025 | 0.0088 +- 0.0013 | 0.009 | 0.010 | 0.010 |
| m2 | 0.035 | 0.037 | 0.038 | 0.0203 +- 0.0020 | 0.011 | 0.012 | 0.012 |
| m3 | 0.062 | 0.069 | 0.069 | 0.0184 +- 0.0023 | 0.026 | 0.028 | 0.028 |
| m4 | 0.082 | 0.088 | 0.089 | 0.0259 +- 0.0017 | 0.028 | 0.030 | 0.030 |
| m5 | 0.029 | 0.031 | 0.031 | 0.0134 +- 0.0012 | 0.011 | 0.012 | 0.012 |
| big_fp32 | 0.070 | 0.074 | 0.075 | 0.0208 +- 0.0018 | 0.028 | 0.030 | 0.030 |
| s_fp32 (attacker) | - | - | - | - | 0.029 | 0.031 | 0.031 |
| pool diagonal mean | 0.046 | 0.050 | 0.050 | - | | | |
| pool off-diagonal mean | 0.010 | 0.011 | 0.011 | random pool_mean 0.0167 +- 0.0004 | | | |
Sources: e1_transfer.csv (80), e1_transfer_steps400.csv, e1_transfer_steps1000.csv, e1_random_baseline.csv.

Other rows, pool_mean at 80 / 1000 steps: s_q2 0.006 / 0.007, s_q3 0.001 / 0.001, s_q4 0.015 / 0.017,
s_ensemble_q 0.007 / 0.008, s_ensemble_all 0.012 / 0.013.
Strongest pool pairs at 1000 steps (vs random level of the column): m3->m4 0.033 (0.026), m3->m2 0.025 (0.020),
m4->m3 0.024 (0.018). Float sources at 1000 steps: s_fp32->m4 0.049 (0.026), s_fp32->big_fp32 0.061 (0.021),
big_fp32->m4 0.048.

evades_ALL_pool: 0.0 in every row at 80, 400 and 1000 steps and in all 5 random trials. Of the 2,000 records, 1,629 are
detected by all six pool models (counted with a scratchpad script on the same sample; the number does not depend on the
step count). 0 of 1,629 -> 95% upper bound 0.18% per run (rule of three; exact Clopper-Pearson gives the same). The runs
reuse the same records, so the bounds do not combine, and the bound only holds inside these knob ranges.

Knob-range ceiling (scratchpad check, NOT a committed result): share of detected records that evade at ANY of the 32
corners of the knob box or 2,000 random settings per record: m4 0.105 (corners alone 0.086), m1 0.030 (corners 0.029).
The 1000-step hill climb reaches 0.089 and 0.025, i.e. most of that ceiling.

### What E1 shows (and does not)
- The diagonal plateaus at 0.050 (0.046 -> 0.050 -> 0.050). The cause is the knob ranges, not the search: even a
  near-exhaustive search evades only about 3% (m1) to 10.5% (m4) of detected attacks.
- Within the pool, transfer (off-diagonal mean 0.011) is BELOW the random-knob level (0.0167); the strongest pairs are only
  slightly above random. E1 therefore gives no evidence of transfer between pool members and no evidence that the pool
  is diverse; it does not refute diversity either. The attack cannot get far enough above random to tell.
- Evasions crafted on float models (s_fp32, big_fp32) transfer at about 2-3x the random level: the only transfer signal.
  Quantised surrogates and ensembles stay at or below random.
- No record evaded all six pool models (upper bound 0.18% per run, inside these knob ranges).
- Widening the knob ranges would need a change to common/features.py (frozen); not done.
