# ml/ (P3; `e4_fingerprint.py` is run by P4)
1. Dataset: UNSW-NB15 "training and testing sets" (two CSV files, about 257,000 records in total) from the UNSW Canberra
   dataset page: https://research.unsw.edu.au/projects/unsw-nb15-dataset . Put both CSVs in `data/unsw/`. Cite Moustafa & Slay 2015.
2. `prepare.py` -> `train_pool.py` -> sign the pack -> `train_stage2.py` (see the top-level README).
3. Experiments, run from the repo root (`python ml/e1_transfer.py` ...): `e1_transfer.py` (pool diversity), `e2_rotation.py` (static vs rotating under
   attack), `e4_fingerprint.py` (can the active model be identified?). Each writes a CSV into `results/`.
4. `--drop-shortcuts` on `train_pool.py` zeroes the TTL features that are known testbed artefacts; report both variants.
`make_synth.py` creates FAKE data for trying the code only.
