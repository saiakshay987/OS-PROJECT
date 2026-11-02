# Working together

## Branches
- `main` is always demo-able. Nobody pushes to it directly; it only changes through a pull request.
- Each person works on `p<N>/<topic>` branches, for example `p1/hls-vad`, `p2/petalinux-boot`, `p3/model-v1`, `p4/nftables`.
- Keep branches short (1-2 days), then open a PR and merge. Long-lived branches cause painful merges.

```bash
git clone <repo-url> && cd vaani-os
git checkout -b p1/hls-vad            # your own branch
# ...work, then:
git add -A && git commit -m "hls: add VAD state"
git push -u origin p1/hls-vad         # open a PR on GitHub into main
git pull --rebase origin main         # do this daily to stay current
```

## Rules
1. **Only edit your own folders** (see the ownership table in the README). Need a change elsewhere? Ask the owner or open an issue.
2. **`common/features.py` is frozen** after Day 2. Any change there needs all four people to agree, because the FPGA, the board and the model depend on it. After a change, regenerate `mel_fb.h` and the test vectors:
   `python common/features.py` and `python common/make_vad_test.py` (needs the Speech Commands dataset in `data/`).
3. **Never commit build output**: PetaLinux `build/` and `images/`, Buildroot `output/`, Vivado `*.runs/` and `*.cache/`. Commit recipes (Tcl, defconfig, config fragments, project-spec) so a stranger can rebuild.
4. Small binaries others need (`.bit.bin`, `.xsa`, `model.onnx`) are OK, a few MB each. Datasets and SD-card images are not.
5. One PR needs one review from someone else, and `pytest` must pass (CI runs it).
6. Keep a `NOTES.md` inside your folder: every command that worked, every error and its fix. It becomes your report section.
7. Never commit secrets. The MQTT password lives only in `/data/voice.conf` on the board (see `app/board/voice.conf`).

## Commit messages
Short and prefixed by area: `hw:`, `kernel:`, `os:`, `app:`, `ml:`, `sec:`, `bench:`, `report:`, `docs:`.

## Tags
`v0.1` first end-to-end demo (Day 8-9), `v1.0` final submission (Day 15).
