# Working together (5 days, so keep it simple)

- `main` is always demo-able. Change it only through pull requests; one teammate reviews; `pytest -q` must pass.
- Branches: `p<N>/<topic>`, e.g. `p3/pool-training`. Merge at least once a day. `git pull --rebase origin main` every morning.
- Edit only your own folders (table in the README). `common/` is frozen after Day 1: changing it needs all four to agree,
  then retrain, re-sign and regenerate the HLS code.
- Never commit: datasets (`data/`), build output (PetaLinux `build/` `images/`, Buildroot `output/`, Vivado/HLS project
  folders), or **`keys/pool_priv.pem`**. The public key and small results (CSV, PNG, model packs of a few hundred KB) are fine.
- Every result in the report must name the commit, the command and the dataset that produced it. Keep `NOTES.md` in `notes/`.
- Commit prefixes: `hw:` `kernel:` `os:` `app:` `ml:` `sec:` `bench:` `report:` `docs:`. Tags: `v0.1` first end-to-end run, `v1.0` submission.
