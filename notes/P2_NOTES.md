# P2 notes (PetaLinux image, appliance service)

Every command that worked, every error and its fix, with dates. Every number with the commit and command that produced it.

## 1. Environment and versions

| Item | Value |
|---|---|
| Host | Ubuntu 22.04.5, laptop Yoga Slim 7 |
| PetaLinux | 2024.1, ZC702 BSP (Zynq-7020) |
| Kernel | 6.6.10-xilinx |
| Boot | QEMU: `petalinux-boot --qemu --kernel`; root filesystem is in RAM (initramfs) |
| QEMU network | user-mode NAT: guest 10.0.2.15, host/laptop 10.0.2.2 |
| Board | No PYNQ board. The FPGA swap is imitated (`SWAP_MS`, default 207 ms) |
| Python (laptop) | 3.10.12, venv `.venv` with paho-mqtt 2.2.0 |
| Python MQTT (image) | paho-mqtt 1.x (python3-paho-mqtt from the PetaLinux rootfs) |
| OS-PROJECT repo | `~/Desktop/OS-PROJECT`, branch `p2/e3-hardening-results`, E3 results committed in `61ead56` at the time of writing (clone of github.com/saiakshay987/OS-PROJECT). The paho 1.x fix (PR #7, `p2/paho1-compat`, `b9a26ad`) was merged into `main` on 20 Nov 2026 and is now also in this branch after rebasing |
| PetaLinux project | `~/plx/ids-os`, **not a git repository**, so there is no commit hash. Its state is described below and by the files in `os/petalinux/` and `kernel/` |
| Disk | Tight: about 72-76 GB free; installer 3.1 GB (deleted afterwards) |

What is set up in `~/plx/ids-os`:

- **Init manager = systemd**, set with `petalinux-config -c rootfs` -> Image Features -> Init-manager (`CONFIG_Init-manager-systemd=y`).
- `project-spec/meta-user/conf/petalinuxbsp.conf` contains `INHERIT += "rm_work"` (saves disk).
- `user-rootfsconfig` + `rootfs_config`: `python3`, `python3-numpy`, `python3-paho-mqtt`, `nftables`, `openssl-bin` all `=y`.
- Kernel fragment: `recipes-kernel/linux/linux-xlnx_%.bbappend` adds `SRC_URI += file://ids.cfg`. `ids.cfg` is copied from `kernel/ids.cfg` in this repo (1066 bytes). nftables support in the kernel was verified.
- Recipe `project-spec/meta-user/recipes-apps/ids-app/` (`ids-app.bb` + `files/`; copy in `os/petalinux/ids-app.bb`) installs:
  - `/opt/ids/{idsd.py,fpga_regs.py,qmlp.py,modelpack.py}`
  - `/etc/ids/{ids.conf,pool_pub.pem}`
  - `/etc/nftables.conf`
  - `ids.service`
  - the signed factory pack at `/opt/ids/pool-factory` (P4's signed-pack-v1). **No private key is in the image.**
- `ids.service`: `User=ids`, `AmbientCapabilities=CAP_NET_ADMIN`, `ExecStartPre=+/usr/sbin/nft -f /etc/nftables.conf`.
- `nftables.conf`: default-deny; a `blocked` set (`ipv4_addr`, `flags timeout`, 60 s entries) filled by the daemon; MQTT port 1883 allowed out.
- The daemon's default `--pool` is `/data/pool` (absent), so it falls back to the factory pack. Signed-pack verification works on the device: the guest log line is `pack OK: /opt/ids/pool-factory version 1 with 6 models`.
- Laptop side: Mosquitto with `app/laptop/mosquitto.conf` (listener 1883 0.0.0.0, anonymous). The guest reaches it at 10.0.2.2. Topics: `net/flows`, `ids/alert`, `ids/status`, `ids/verdict`.

## 2. Commands that worked, in order (20 Nov 2026)

TODO: the exact command history was not provided and could not be verified from files. Below is what is known; the order follows the build/run flow. Fill in or correct from shell history (`history | less`) before handing off.

1. Configure init manager: `cd ~/plx/ids-os && petalinux-config -c rootfs` -> Image Features -> Init-manager -> systemd. (After the failed attempt in section 3, item 1.)
2. Build: `petalinux-build` (first full build 37m13s; later builds 3m14s, 4m40s, 1m26s).
3. Boot in QEMU: `petalinux-boot --qemu --kernel`. Leave QEMU with **Ctrl-a x**.
4. Laptop broker: `mosquitto -c app/laptop/mosquitto.conf` (TODO: confirm this was the exact invocation).
5. Laptop replay (flags from `replay.py --help`: `--broker --transport {mqtt,udp} --host --port --data --n --rate --attackers --seed --csv --label`): `python3 app/laptop/replay.py --n 3000 --rate 300 ...` (TODO: paste the full command including `--data`, `--attackers`, `--seed`, `--csv`, `--label` if used; the defaults were not recorded).
6. Tests on the laptop: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` (5 passed).
7. Inside the guest, firewall set check (root): `sudo nft list set inet filter blocked`, or `while true; do sudo nft list set inet filter blocked; sleep 10; done` while a replay is running.
8. Journal checks: `journalctl -u ids` and grep for `BLOCK 10.0.9.` / `BLOCK 10.0.0.` (TODO: paste exact command).

## 3. Errors and their fixes

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | Build failed in `do_rootfs`: `package systemd ... is filtered out by exclude filtering` | I forced systemd with 4 lines in `petalinuxbsp.conf` (`DISTRO_FEATURES:append systemd`, `DISTRO_FEATURES_BACKFILL_CONSIDERED sysvinit`, `VIRTUAL-RUNTIME_init_manager`, `VIRTUAL-RUNTIME_initscripts`) | Removed those lines; set systemd via `petalinux-config -c rootfs` -> Image Features -> Init-manager |
| 2 | Could not find the ZC702 BSP; wrong AMD docs page (EDF) | BSPs are not on the page I opened | BSPs are under the "PetaLinux Board Support Packages" tab of the downloads page |
| 3 | Laptop commands typed in the QEMU guest (happened twice) | Confusing the guest shell with the laptop shell | Leave QEMU with Ctrl-a x, run on the laptop |
| 4 | `pytest` crashed | ROS pytest plugins autoloaded | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` (5 passed) |
| 5 | `idsd.py` crashed on the image | Image has paho-mqtt 1.x, laptop venv has 2.x; the callback API differs | try/except compatibility patch in `app/appliance/idsd.py`. **TELL TEAM:** the fix was on branch `p2/paho1-compat`, commit `b9a26ad`; PR #7 ("Fix idsd.py crash on paho-mqtt 1.x (image) while keeping 2.x (laptop)") was merged into `main` on 20 Nov 2026. The fix is in `main` and is now also in this branch after rebasing |
| 6 | Disk space running out | build tree is large | `INHERIT += "rm_work"`; deleted the 3.1 GB installer |
| 7 | `nft list set` as a normal user in the guest: `Operation not permitted` | Needs root | Expected and good (see section 5, hardening evidence). Use `sudo` |
| 8 | `blocked` set looks empty | Entries expire after 60 s | Run the replay and list the set within 60 s, or loop `sudo nft list set inet filter blocked` every 10 s |
| 10 | With the read-only root, the forced first-login password change failed: `Authentication token manipulation error` | The expired-password flow needs to write `/etc/shadow`, which is read-only | Bake a non-expired password at build time with an `EXTRA_USERS_PARAMS` override in `petalinuxbsp.conf`. The password is lab-only; it is **not** written here. It is in `petalinuxbsp.conf` and was shared with the team directly |
| 9 | **Cross-talk:** E3 results contaminated; the `blocked` set held all 50 benign hosts | Guest `ids` service and a laptop-side `idsd.py` share the same Mosquitto topics, so `bench/e3_blind_window.sh` mixed in the guest's alerts and blocks | Only ONE daemon may answer on the broker at a time. Before E3: stop QEMU or `systemctl stop ids` in the guest. Before QEMU measurements: stop the laptop daemon. The contaminated E3 CSV was deleted and E3 was rerun clean on 20 Nov at about 16:18 IST |

## 4. Numbers

All QEMU numbers: `replay.py` through the QEMU image, 20 Nov 2026, 3000 records at 300/s, real test set, signed-pack-v1, commit `b9a26ad` (OS-PROJECT). Command: `python3 app/laptop/replay.py --n 3000 --rate 300 [other flags: TODO exact command]`. The PetaLinux project has no commit (not a git repo).

| Number | Value | Command that produced it | Commit |
|---|---|---|---|
| Records sent | 3000 in 10.0 s (1912 attacks) | `replay.py --n 3000 --rate 300` | b9a26ad |
| Alerts | 1739 | same | b9a26ad |
| TP / FP / FN / TN | 1685 / 54 / 227 / 1034 | same | b9a26ad |
| Recall | 0.881 | same | b9a26ad |
| FPR | 0.050 (calibrated 5% per record held) | same | b9a26ad |
| Latency record-sent to alert-seen (through QEMU NAT + MQTT), median | 21.4 ms | same | b9a26ad |
| Latency p95 | 195.0 ms (cause: bursts of newly blocked sources, reproduced with the service; see E3-QEMU (f), section 5. Not swaps) | same | b9a26ad |
| Appliance status after run | blocks 42, swaps 95, member m3, verdicts 0 (stage-2 server not running) | `ids/status` topic | b9a26ad |
| Journal: attackers blocked | `BLOCK 10.0.9.` = 8 (all of 10.0.9.1-8) | guest `journalctl` grep (TODO exact command) | b9a26ad |
| Journal: benign hosts blocked | `BLOCK 10.0.0.` = 34 of 50 | same | b9a26ad |
| Second capture of blocked set (within 60 s of a replay) | 8 attackers + 30 benign hosts, each `timeout 1m` with an expires countdown | `sudo nft list set inet filter blocked` (loop) | b9a26ad |
| Third capture of blocked set (after two replays, manual daemon as root, `--block nft`, rotation off) | 8 attackers + 45 benign hosts = 53 entries, `timeout 1m` | `sudo nft list set inet filter blocked` | b9a26ad |
| Screenshot | `results/firewall_blocked.png` (shows the third capture) | n/a | n/a |
| Build time, first full build | 37m13s | `petalinux-build` | no commit (not a git repo) |
| Build times, later | 3m14s, 4m40s, 1m26s | `petalinux-build` | no commit |
| `build/` size | 17 GB, measured 20 Nov 2026 on the current image (build 3). The earlier 15 GB figure is from an earlier measurement and was not reproduced; the cause of the difference is unverified | `du -sh ~/plx/ids-os/build` | no commit |
| `images/linux` size | 577 MB in total (590504 KB in the `ls -l` header), measured 20 Nov 2026 on the current image (build 3); it was 587 MB at the previous build and changes with each build. The earlier 209 MB figure does not match any single file now; the cause is unverified. Largest files: `rootfs.ext4` 186M, `rootfs.cpio` 125M, `rootfs.jffs2` 54M, `rootfs.tar.gz` 48M, `image.ub` 47M, `rootfs.cpio.gz.u-boot` 43M, `rootfs.cpio.gz` 43M, `vmlinux` 13M, `u-boot.elf` 8.3M, `uImage` 4.4M, `zImage` 4.4M. The QEMU boot uses the initramfs (`rootfs.cpio.gz`, 43M compressed) as its RAM root; `rootfs.ext4` (186M) is the candidate for an SD-card root on the board | `du -sh ~/plx/ids-os/images/linux` | no commit |
| `image.ub` (kernel + rootfs FIT, used for boot) | 49,159,852 B (about 46.9 MiB; 1 MiB = 1048576 B) | `ls -l ~/plx/ids-os/images/linux` | no commit |
| `zImage` | 4,560,016 B (about 4.3 MiB) | same | no commit |
| `rootfs.cpio` (uncompressed initramfs) | 130,197,504 B (about 124.2 MiB) | same | no commit |
| `rootfs.cpio.gz` | 44,571,450 B (about 42.5 MiB) | same | no commit |
| `rootfs.ext4` | 194,957,312 B (about 185.9 MiB) | same | no commit |
| `rootfs.tar.gz` | 49,466,177 B (about 47.2 MiB) | same | no commit |
| Image build timestamp | `image.ub` and rootfs files dated 20 Nov 18:42 (build 3; `system.dts` and `config` 18:41-18:42) | `ls -l` | no commit |

**E3 results** (blind window of a model swap). Source: `results/e3_blind_window.csv`, 28 rows, produced by `bench/e3_blind_window.sh` on the laptop daemon (no QEMU): `--rotate fixed --rotate-s 5 --seed 1`, replay 30 s per row (records = rate x 30). Every value below is computed from the CSV by a short Python snippet, not typed by hand. Commit of the repo when run: TODO (CSV is untracked; record `git rev-parse --short HEAD` when it is committed). Recall/FPR are per record; alert p50/p95 are record-sent to alert-seen in ms.

| Swap (ms) | Fallback | Rate (/s) | Records | Recall | FPR | Alert p50 (ms) | Alert p95 (ms) | Fallback recs | Unclassified | Held |
|---|---|---|---|---|---|---|---|---|---|---|
| 34 | arm | 100 | 3000 | 0.875 | 0.043 | 3.4 | 4.7 | 30 | 0 | 0 |
| 34 | arm | 500 | 15000 | 0.873 | 0.044 | 3.5 | 4.8 | 150 | 0 | 0 |
| 34 | arm | 1500 | 45000 | 0.873 | 0.044 | 5.3 | 7.2 | 0 | 0 | 0 |
| 34 | hold | 100 | 3000 | 0.875 | 0.043 | 2.7 | 3.9 | 0 | 0 | 30 |
| 34 | hold | 500 | 15000 | 0.873 | 0.044 | 3.5 | 5.3 | 0 | 0 | 0 |
| 34 | hold | 1500 | 45000 | 0.873 | 0.044 | 5.6 | 7.5 | 0 | 0 | 450 |
| 34 | open | 100 | 3000 | 0.867 | 0.042 | 3.0 | 4.3 | 0 | 30 | 0 |
| 34 | open | 500 | 15000 | 0.864 | 0.044 | 3.7 | 5.3 | 0 | 150 | 0 |
| 34 | open | 1500 | 45000 | 0.864 | 0.043 | 5.1 | 7.0 | 0 | 450 | 0 |
| 207 | arm | 100 | 3000 | 0.875 | 0.043 | 2.8 | 4.1 | 120 | 0 | 0 |
| 207 | arm | 500 | 15000 | 0.873 | 0.044 | 3.7 | 5.1 | 625 | 0 | 0 |
| 207 | arm | 1500 | 45000 | 0.873 | 0.044 | 5.0 | 6.8 | 1800 | 0 | 0 |
| 207 | hold | 100 | 3000 | 0.875 | 0.043 | 2.8 | 4.9 | 0 | 0 | 120 |
| 207 | hold | 500 | 15000 | 0.873 | 0.044 | 3.8 | 5.8 | 0 | 0 | 600 |
| 207 | hold | 1500 | 45000 | 0.873 | 0.044 | 5.1 | 8.3 | 0 | 0 | 2175 |
| 207 | open | 100 | 3000 | 0.834 | 0.039 | 2.7 | 3.9 | 0 | 150 | 0 |
| 207 | open | 500 | 15000 | 0.838 | 0.042 | 3.5 | 4.8 | 0 | 600 | 0 |
| 207 | open | 1500 | 45000 | 0.833 | 0.041 | 4.8 | 6.7 | 0 | 2100 | 0 |
| 550 | arm | 100 | 3000 | 0.875 | 0.043 | 3.0 | 4.4 | 330 | 0 | 0 |
| 550 | arm | 500 | 15000 | 0.872 | 0.044 | 3.4 | 4.9 | 1650 | 0 | 0 |
| 550 | arm | 1500 | 45000 | 0.872 | 0.044 | 5.3 | 7.3 | 4950 | 0 | 0 |
| 550 | hold | 100 | 3000 | 0.875 | 0.043 | 3.5 | 305.0 | 0 | 0 | 330 |
| 550 | hold | 500 | 15000 | 0.873 | 0.044 | 3.8 | 310.1 | 0 | 0 | 1625 |
| 550 | hold | 1500 | 45000 | 0.873 | 0.044 | 5.6 | 313.7 | 0 | 0 | 4950 |
| 550 | open | 100 | 3000 | 0.775 | 0.035 | 3.0 | 4.8 | 0 | 330 | 0 |
| 550 | open | 500 | 15000 | 0.772 | 0.039 | 3.7 | 5.3 | 0 | 1650 | 0 |
| 550 | open | 1500 | 45000 | 0.776 | 0.039 | 5.1 | 7.1 | 0 | 4950 | 0 |
| none (no rotation) | n/a | 500 | 15000 | 0.843 | 0.026 | 3.9 | 5.4 | 0 | 0 | 0 |

Each rotating row had 7 swaps (`swaps` column) in 30 s.

**Fraction of records handled by the fallback or left unclassified**, (fallback_recs + unclassified + held) / recs, over the 9 rows (3 fallbacks x 3 rates) of each swap time, next to the prediction swap_ms / 5000 (swap time divided by the 5 s rotation period):

| Swap (ms) | Predicted swap_ms/5000 | Measured, all 9 rows pooled | Measured, min - max over rows |
|---|---|---|---|
| 34 | 0.68% | 0.68% | 0.00% - 1.00% |
| 207 | 4.14% | 4.39% | 4.00% - 5.00% |
| 550 | 11.00% | 10.99% | 10.83% - 11.00% |

**Batch granularity (why swap 34 ms looks coarse):** `replay.py` publishes records in batches of rate x 0.05, i.e. 5, 25 and 75 records at 100, 500 and 1500/s, one batch every 50 ms. The swap-34 fallback counts in the CSV (30, 150, 450) equal 6 x the batch size, so a swap that overlaps a batch marks the whole batch. Per-row fractions therefore move in batch-sized steps (0% or 1.00% at swap 34 ms, never near the predicted 0.68%), and only the pooled fraction is meaningful. (Batch sizes taken from the replay design as described by the author; not re-checked in `replay.py` for this note.)

**E3 in QEMU** (guest daemon, real service image). Source: `results/e3_qemu.csv`, 14 rows, 20 Nov 2026, replay 30 s per row (records = rate x 30), rotation `fixed`, 5 s period, swap 207 ms, seed 1 unless stated. Every value below is computed from the CSV by a Python snippet. Repo commit when run: TODO (CSV untracked). Alert p50/p95 = record-sent to alert-seen in ms, measured with the **guest clock** (see section 5, E3-QEMU (g)).

**Cumulative counters.** In `e3_qemu.csv` the columns `swaps`, `fallback_recs`, `unclassified`, `held` (and `recs`) are cumulative since the daemon start. The daemon was **not** restarted between the 100/s and the 500/s run of a mode, nor between the three `svc_*` runs. Per-run values are differences, e.g. arm 500/s fallback = 810 - 135 = 675; svc cold/warm/rewarm fallback = 0, 135 - 0 = 135, 135 - 135 = 0. The `blocks` counter is not a column of the CSV; the block counts quoted below (svc new blocks 38, 42 - 38 = 4, 70 - 42 = 28) come from the daemon status as cumulative values, as reported by the author, and are not recomputed here. `recs` is also cumulative and is not reliable per run (e.g. off_nft 500/s: 18000 - 2880 = 15120 > 15000 sent), so it is not used.

| Label | Records | TP / FP / FN / TN | Recall | FPR | Alert p50 (ms) | Alert p95 (ms) | Per-run swaps | Per-run fallback / unclassified / held |
|---|---|---|---|---|---|---|---|---|
| arm, 100/s | 3000 | 1657 / 45 / 255 / 1043 | 0.867 | 0.041 | 13.0 | 17.1 | 3 | 135 / 0 / 0 |
| arm, 500/s | 15000 | 8424 / 246 / 1151 / 5179 | 0.880 | 0.045 | 25.6 | 33.6 | 4 | 675 / 0 / 0 |
| hold, 100/s | 3000 | 1691 / 49 / 221 / 1039 | 0.884 | 0.045 | 12.3 | 38.1 | 6 (cumulative) | 0 / 0 / 135 |
| hold, 500/s | 15000 | 8359 / 228 / 1216 / 5197 | 0.873 | 0.042 | 26.6 | 206.1 | 3 | 0 / 0 / 675 |
| open, 100/s | 3000 | 1575 / 50 / 337 / 1038 | 0.824 | 0.046 | 12.5 | 15.8 | 5 (cumulative) | 0 / 135 / 0 |
| open, 500/s | 15000 | 8063 / 253 / 1512 / 5172 | 0.842 | 0.047 | 24.5 | 32.5 | 3 | 0 / 675 / 0 |
| off (log), 100/s | 3000 | 1607 / 24 / 305 / 1064 | 0.841 | 0.022 | 12.6 | 16.1 | 0 | 0 / 0 / 0 |
| off (log), 500/s | 15000 | 8075 / 140 / 1500 / 5285 | 0.843 | 0.026 | 25.4 | 33.5 | 0 | 0 / 0 / 0 |
| off (nft), 100/s | 3000 | 1607 / 24 / 305 / 1064 | 0.841 | 0.022 | 13.0 | 28.5 | 0 | 0 / 0 / 0 |
| off (nft), 500/s | 15000 | 8075 / 140 / 1500 / 5285 | 0.843 | 0.026 | 24.6 | 46.2 | 0 | 0 / 0 / 0 |
| svc cold, 300/s | 3000 | 1656 / 41 / 256 / 1047 | 0.866 | 0.038 | 20.8 | 191.6 | 9 | 0 / 0 / 0 |
| svc warm, 300/s | 3000 | 1659 / 45 / 253 / 1043 | 0.868 | 0.041 | 18.9 | 23.8 | 1 | 135 / 0 / 0 |
| svc re-warm, 300/s | 3000 | 1607 / 24 / 305 / 1064 | 0.841 | 0.022 | 19.4 | 171.0 | 5 | 0 / 0 / 0 |

The `arm`, `hold`, `open` and `off (log)` rows used `--block log`; `off (nft)` and the `svc_*` rows block with nft (`off_log` / `off_nft` run by hand as root; `svc_*` run through the systemd service with the image defaults poisson / 30 s, arm). The per-run swap counts for hold 100/s and open 100/s include swaps before the run and are shown only for completeness. Records handled by the fallback / left unclassified / held: 4.5% in every rotating row (135/3000 and 675/15000).

**Laptop vs QEMU**, swap 207 ms (laptop rows: `results/e3_blind_window.csv`, `swap207_*` and `no_rotation_rate500`):

| Mode | Rate | Laptop recall | QEMU recall | Laptop FPR | QEMU FPR | Laptop p50 / p95 (ms) | QEMU p50 / p95 (ms) |
|---|---|---|---|---|---|---|---|
| arm | 100/s | 0.875 | 0.867 | 0.043 | 0.041 | 2.8 / 4.1 | 13.0 / 17.1 |
| arm | 500/s | 0.873 | 0.880 | 0.044 | 0.045 | 3.7 / 5.1 | 25.6 / 33.6 |
| hold | 100/s | 0.875 | 0.884 | 0.043 | 0.045 | 2.8 / 4.9 | 12.3 / 38.1 |
| hold | 500/s | 0.873 | 0.873 | 0.044 | 0.042 | 3.8 / 5.8 | 26.6 / 206.1 |
| open | 100/s | 0.834 | 0.824 | 0.039 | 0.046 | 2.7 / 3.9 | 12.5 / 15.8 |
| open | 500/s | 0.838 | 0.842 | 0.042 | 0.047 | 3.5 / 4.8 | 24.5 / 32.5 |
| off | 500/s | 0.843 | 0.843 (log and nft) | 0.026 | 0.026 | 3.9 / 5.4 | 25.4 / 33.5 (log), 24.6 / 46.2 (nft) |


## 5. Findings and limitations

- **Design limitation: first-alert blocking.** The daemon blocks a source on its FIRST alert. With a 5% per-record FPR, a benign host that sends many records almost surely trips it: 34/50 benign hosts were blocked in the journal run (30/50 in the second capture); about 33 are expected from 54 FPs over 50 hosts. This is not a bug and was not fixed after the feature freeze (Thu 23:59). Suggested future work: block only after k alerts within a time window, or use a score threshold.
- **Detection:** the calibrated 5% FPR holds, recall is 0.88, and 8/8 attackers were blocked.
- **Hardening evidence:** (a) unprivileged `nft` access is denied (`Operation not permitted`), so only root and the `ids` service (CAP_NET_ADMIN) can read or change the ruleset; (b) the service runs as user `ids`, not root; (c) no private signing key is in the image.
- **One daemon at a time:** the guest service and a laptop `idsd.py` answer on the same topics; see section 3, item 9. E3 and QEMU measurements must not overlap.
- **Imitated FPGA:** no board, so swap blind windows use `SWAP_MS` (default 207 ms); latency and recall are not FPGA measurements.
- **Latency includes QEMU NAT and MQTT**, not only the model. The p95 tail follows newly blocked sources (E3-QEMU (f)); why the service is slower than a manual nft run is open.
- **paho patch:** merged into `main` on 20 Nov 2026 (PR #7), now also in this branch after rebasing (section 3, item 5).

- **E3 (a) arm absorbs the swap.** With the `arm` fallback, recall is 0.872-0.875 and alert p95 is 4.1-7.3 ms across all 3 swap times and 3 rates, i.e. no change when the swap grows from 34 to 550 ms (11% of records go to the fallback at 550 ms).
- **E3 (b) hold keeps recall but adds a latency tail.** `hold` recall is the same as `arm` (0.873-0.875 at 550 ms), but alert p95 at swap 550 ms is 305.0-313.7 ms (p50 stays 3.5-5.6 ms). The tail shows in p95 only when more than 5% of records are held: at 550 ms the held share is 10.8-11.0% (p95 jumps), at 207 ms it is 4.0-4.8% (p95 4.9-8.3 ms, no tail).
- **E3 (c) open loses recall in proportion to swap_ms / rotate period.** Compared with `arm` at 500/s, `open` loses 1.0% / 4.1% / 11.4% of recall (relative) at swap 34 / 207 / 550 ms, against predicted 0.68% / 4.14% / 11.00%. Open-fallback recall: swap 34 ms 0.864-0.867, 207 ms 0.833-0.838, 550 ms 0.772-0.776. FPR also falls (unclassified records raise no alert), which is not a benefit.
- **E3 (d) alert latency covers only records that raised an alert.** p50/p95 are computed over alerts, so records left unclassified in `open` (and benign records) are not in the latency numbers; a lower p95 under `open` does not mean those records were handled quickly.
- **E3 (e) no-rotation baseline is a different operating point.** `no_rotation_rate500` has recall 0.843 and FPR 0.026, while rotating rows sit near recall 0.87 / FPR 0.044. **Cause found (closes the earlier TODO):** both rotation-off runs report member `m1` (member name as reported by the author from the daemon status; not a CSV column), so the baseline is one single, stricter member (FPR 0.026, recall 0.843), while rotation mixes six members (recall 0.873, FPR 0.044). These are different operating points; no claim is made that rotation improves detection.
- **E3 (f) image defaults.** The image defaults are `ROTATE=poisson`, `ROTATE_S=30` (`app/appliance/ids.conf`), swap 207 ms, `arm`. Expected blind time is 207 ms / 30 s = 0.7%, so swaps cannot explain the 195.0 ms p95 seen earlier in QEMU. See E3-QEMU (f) below for the reproduction and the actual cause.

**E3 in QEMU: findings** (data in section 4, "E3 in QEMU").

- **E3-QEMU (a) the integer model is deterministic across x86 and emulated ARM.** Rotation-off counts at 500/s (TP 8075, FP 140, FN 1500, TN 5285) are identical in `qemu_off_log_rate500`, `qemu_off_nft_rate500` and the laptop row `no_rotation_rate500`.
- **E3-QEMU (b) baseline TODO closed:** see E3 (e) above (member `m1` alone vs six members).
- **E3-QEMU (c) open:** the unclassified fraction is 4.5% (675/15000 at 500/s, 135/3000 at 100/s). Recall loss against arm is 0.038 at 500/s (0.880 - 0.842) and 0.043 at 100/s, as the swap/period model predicts. The nominal 207 ms / 5 s gives 4.14%; the measured 4.5% matches a swap of about 450 ms every 10 s, i.e. the effective values in (g), not the nominal ones.
- **E3-QEMU (d) hold:** alert p95 is 206.1 ms at 500/s in QEMU against 33.6 ms for arm (laptop: 5.8 vs 5.1 ms at swap 207 ms). Held records wait for the swap, so they form the tail; 4.5% held is not under the 5% that p95 ignores, which matches E3 (b).
- **E3-QEMU (e) nft blocking costs about 12 ms at p95.** `off_nft` vs `off_log`, run by hand as root: 28.5 vs 16.1 ms at 100/s (+12.4) and 46.2 vs 33.5 ms at 500/s (+12.7). p50 and the detection counts are unchanged.
- **E3-QEMU (f) the 195 ms p95 is REPRODUCED with the real service** (poisson / 30 s, arm, nft, 300/s, 3000 records):

  | Run | p50 (ms) | p95 (ms) | New blocks |
  |---|---|---|---|
  | cold | 20.8 | 191.6 | 38 |
  | warm | 18.9 | 23.8 | 4 (42 - 38) |
  | re-warm (after waiting 40 s; blocks are forgotten after 30 s) | 19.4 | 171.0 | 28 (70 - 42) |

  The tail follows the number of **newly blocked sources**, not a cold start and not swaps (the warm run had 1 swap and the re-warm run 5, the cold run 9). Mechanism, supported by reading `block()` in `idsd.py`: it runs `subprocess.run` of `nft` synchronously in the main loop, so classification stalls during a burst of blocks. **Fix for later (not done, feature freeze):** run the nft call in a worker thread or use a persistent netlink connection. **OPEN, untested:** the same nft blocking run by hand as root adds only about 12 ms (e), so why the service is slower is unknown; candidates are journald logging of each line, the service sandbox (a hypothesis that has now been seen, in the hardened-vs-unhardened latency below, but not isolated), and the 300/s rate. Note also that `svc_rewarm` produced the same counts as the `off` runs (1607 / 24 / 305 / 1064, recall 0.841, FPR 0.022); not investigated.
- **E3-QEMU (g) guest clock (UNVERIFIED).** In QEMU each swap held about 450 ms of traffic (675 held / 3 swaps = 225 records at 500/s) and swaps came about every 10 s instead of every 5 s (3 swaps per 30 s run at 100/s, 3-4 at 500/s). This suggests the guest clock runs slower than real time under load. TODO: compare guest and laptop `date` over 2 minutes. Until then treat QEMU timing as guest-clock timing.
- **Firewall evidence:** `results/firewall_blocked.png` shows the `blocked` set after two replays (manual daemon run as root with `--block nft`, rotation off): 8 attackers + 45 benign hosts = 53 entries, `timeout 1m`.
- **On-device signature verification:** the guest log shows `pack OK: /opt/ids/pool-factory version 1 with 6 models`.

## Baseline image measurements (before hardening), 20 Nov 2026, emulated ARM in QEMU, NOT hardware speed

Command: `sh /tmp/m.sh petalinux-before-hardening` (the script is `bench/measure_image.sh` pasted into the guest, because the guest firewall blocks `wget`).

CSV line:

```
petalinux-before-hardening,6.6.10-xilinx-v2024.1-g3af4295e00ef,1807.15,36996,0,69,1,23,NA,17,""
```

| Metric | Value | Note |
|---|---|---|
| Kernel | 6.6.10-xilinx-v2024.1-g3af4295e00ef | |
| Uptime at measurement (s) | 1807.15 | The image had been up about 30 min; field 3 of `bench/measure_image.sh` is `uptime_s`, not boot time. |
| Memory used | 36996 KB (about 36 MiB) | busybox `free` reports KB. `free` showed total 1029224 and used 36484 KB; the CSV value was taken at a slightly different moment. |
| Root used | 0 | The root is `rootfs on / type rootfs (rw)`, in RAM, so there is no disk usage to report. |
| Processes | 69 | |
| Kernel modules | 1 | |
| Listening TCP/UDP sockets | 23 (12 tcp + 11 udp) | `netstat -tuln` |
| Packages | NA | No package manager in the image. |
| setuid files | 17 | |

Boot time: `systemd-analyze` is not in the image, so it comes from `systemctl show`: `UserspaceTimestampMonotonic` = 1,472,117 us and `FinishTimestampMonotonic` = 13,374,580 us. That is **13.4 s to finish**, of which about 11.9 s is userspace (13,374,580 - 1,472,117 us).
System state: `SystemState=degraded`, 2 failed units: `proc-fs-nfsd.mount` and `nfsserver.service`.

Running services (18): busybox-klogd, busybox-syslog, dbus, getty@tty1, ids, inetd.busybox, nfs-statd, rpcbind, serial-getty@ttyPS0, systemd-journald, systemd-logind, systemd-networkd, systemd-resolved, systemd-timesyncd, systemd-udevd, systemd-userdbd, tcf-agent, user@1000.

Listening sockets:

- sshd is socket-activated (`sshd.socket` listens on `[::]:22`).
- `inetd.busybox` listens on telnet (23) and ftp (21).
- `tcf-agent` on 1534 (tcp and udp).
- `rpcbind` on 111.
- `nfs-statd` on several ports.
- `systemd-resolved` on 53 and 5355.
- DHCP client on udp 68.

Firewall: the nftables ruleset drops all inbound traffic except tcp 22 (rate limited), udp 5555 and icmp. Only ssh is reachable from the network, but the other services are closed **by the firewall, not by removing them**. They are still running and listening inside the guest.

Masked (done on the current image, build 3, by the mask loop in `ids-app.bb`, which symlinks each unit to `/dev/null` in `/etc/systemd/system`): 18 units: `inetd.busybox.service`, `rpcbind.service`, `rpcbind.socket`, `nfs-statd.service`, `nfsserver.service`, `nfs-server.service`, `nfs-mountd.service`, `proc-fs-nfsd.mount`, `tcf-agent.service`, `busybox-klogd.service`, `busybox-syslog.service`, `syslog.socket`, `getty@tty1.service`, `systemd-resolved.service`, `systemd-userdbd.service`, `systemd-userdbd.socket`, `sshd.socket`, `sshd.service` (serial console only). `systemd-timesyncd` is not in the mask list, so it is kept running. P4's sshd drop-in stays in the repo in case remote login is needed. TODO: confirm with P4.

## Image measurements after hardening and pruning, QEMU (emulated ARM, NOT hardware speed)

Fields: `image,kernel,uptime_s,mem_used_mb,root_used_mb,processes,modules,listening_ports,packages,setuid_files,boot`

```
petalinux-hardened,6.6.10-xilinx-v2024.1-g3af4295e00ef,25.47,32524,0,61,1,1,NA,9,""
```

Footnotes:

- `mem_used_mb` is really KB (BusyBox `free -m` reports KB), so 32524 KB is about 31.8 MiB.
- `root_used_mb` is 0 and meaningless on a RAM root.
- `packages` is NA (no package manager).
- `boot` is empty because there is no `systemd-analyze`.
- Uptime was 25 s at measurement, shorter than the baseline's 1807 s.

Comparison, baseline -> now:

| Metric | Before | After |
|---|---|---|
| Running services | 18 | 9 |
| Listening sockets | 23 | 1 (UDP 68, DHCP client only) |
| Failed units | 2 (`nfsserver`, `proc-fs-nfsd.mount`) | 0 |
| SystemState | degraded | running |
| Processes | 69 | 61 |
| Boot finish | 13.4 s | 9.6 s (UserspaceTimestamp 1.47 s -> 1.77 s) |
| RAM used | about 36 MiB | 31.8 MiB |
| setuid files | 17 | 9 |

Running services after hardening and pruning (9): dbus, ids, serial-getty@ttyPS0, systemd-journald, systemd-logind, systemd-networkd, systemd-timesyncd, systemd-udevd, user@1000. `systemd-timesyncd` is kept on purpose. The baseline's 18-service list (section "Baseline image measurements") is unchanged.

The setuid drop (17 -> 9) is **unexplained and not credited to hardening**: masking a unit does not delete files, and the baseline run may have been measured differently. The 9 files now: `unix_chkpwd`, `dbus-daemon-launch-helper`, `sudo`, `newgrp.shadow`, `mount.nfs`, `umount.util-linux`, `su.shadow`, `mount.util-linux`, `busybox.suid`.

## Read-only root, hardening and pruning (QEMU, 20 Nov 2026)

**Read-only root.** The image has `EXTRA_IMAGE_FEATURES += "read-only-rootfs"`. Evidence: `results/read_only_root.png`. Caveat: in QEMU the root is an initramfs in RAM, so this shows that the read-only mechanism works, not a persistent SD/EXT4 root. `/data` is a 64M tmpfs (`nodev,nosuid`) via `data.mount`; on the board it would be a third SD partition. Login problem and fix: section 3, item 10.

**Hardening** (P4's `ids.hardening.conf` and `90-hardening.sysctl.conf`, installed by the `ids-app` recipe). The `ids` service starts, runs as user `ids`, logs `pack OK: /opt/ids/pool-factory version 1 with 6 models`, and can still add nft rules (`results/firewall_blocked_hardened.png`). **Finding:** `ProtectHostname` has no effect because the trimmed kernel lacks `CONFIG_UTS_NS`. P1 and P4 should know.

**Service pruning.** 18 units are masked with `/dev/null` symlinks in `/etc/systemd/system`, installed by the `ids-app` recipe. sshd is masked, so the only way in is the serial console; P4's sshd drop-in stays in the repo and is not installed. Follow-up not done: `/sbin/mount.nfs` is still installed and setuid although NFS is masked; removing the NFS packages from the image would be cleaner.

### Hardening, pruning and latency

QEMU, rate 300, first run after boot, p50 / p95 in ms:

| Variant | p50 | p95 | Notes |
|---|---|---|---|
| Unhardened service, cold | 20.8 | 191.6 | the `svc cold` row in section 4 |
| Hardened | 22.5 | 314.5 | |
| Hardened and masked | 22.7 | 318.6 | recall 0.892, FPR 0.051; rotate poisson, 7 swaps, fallback_recs 0, 43 blocks |

Pruning did not change latency. Hardened vs unhardened p95 differs by roughly 120-130 ms; this is suggestive and the cause is untested. The tail was already traced to bursts of newly blocked sources, where the main loop spawns `nft` synchronously (E3-QEMU (f)). **No claim is made that the sandbox causes the gap.**

## 6. Open TODOs

- DONE: E3 results are committed on branch `p2/e3-hardening-results`, commit `61ead56` at the time of writing (E3 CSVs, console log, firewall and read-only screenshots, the notes).
- TODO: find out why the service is slower than a manual nft run (journald logging per line, 300/s rate, and the service sandbox as a hypothesis: hardened p95 was higher than unhardened, see "Hardening, pruning and latency", but this is not isolated). Test one at a time.
- TODO (future work, not in this freeze): move the `nft` call in `idsd.py` `block()` to a worker thread or a persistent netlink connection.
- TODO: compare guest and laptop `date` over 2 minutes to check the guest clock (E3-QEMU (g)).
- DONE (see "Hardening, pruning and latency"): read-only root with `/data` tmpfs in QEMU; P4's `ids.hardening.conf` and `90-hardening.sysctl.conf` installed; 18 units masked. Not installed on purpose: `10-hardening.sshd.conf` (sshd is masked).
- `results/read_only_root.png` shows `touch /etc/x` failing with "Read-only file system" and `mount` reporting `rootfs on / type rootfs (ro)`.
- TODO: on the board, `/data` should be a third SD partition (`os/petalinux/fstab.example`); not tested, no board.
- TODO (follow-up, not done): remove the NFS packages from the image; `/sbin/mount.nfs` is still installed and setuid although NFS is masked.
- TODO: tell P1 and P4 that `ProtectHostname` has no effect (kernel lacks `CONFIG_UTS_NS`).
- TODO: the guest clock is wrong (journal timestamps read Nov 08) because QEMU has no time sync. Do not quote guest dates; see also E3-QEMU (g).
- TODO: explain the setuid drop 17 -> 9 (unexplained, not credited to hardening).
- Measurements for P4/P1: `bench/measure_image.sh`, `bench/speed.py`, `systemd-analyze`.
- Service list for the attack-surface count: TODO paste `systemctl list-units --type=service` from the guest.
- DONE: PR #7 (`p2/paho1-compat` into `main`) was merged on 20 Nov 2026; the paho note was updated (section 1, section 3 item 5, section 7). The fix is in `main` and is now also in this branch after rebasing.
- Fill section 2 with the exact command history.
- P2 report section.

## 7. Hand-off: what P1 and P4 need from P2

- **Signed factory pack in the image:** `/opt/ids/pool-factory` (P4's signed-pack-v1); public key `/etc/ids/pool_pub.pem`; no private key on the device.
- **QEMU detection numbers (section 4):** recall 0.881, FPR 0.050, TP 1685 / FP 54 / FN 227 / TN 1034, median latency 21.4 ms, p95 195.0 ms (cause: bursts of newly blocked sources, E3-QEMU (f)), 8/8 attackers blocked.
- **Image sizes:** `~/plx/ids-os/images/linux/image.ub` 49,159,852 B; `rootfs.cpio.gz` 44,571,450 B; `rootfs.ext4` 194,957,312 B (build 3).
- **E3 data:** `results/e3_blind_window.csv` (28 rows, laptop daemon) and the table in section 4; findings E3 (a)-(f) in section 5. QEMU repeat: `results/e3_qemu.csv` (14 rows, cumulative counters, see section 4) and findings E3-QEMU (a)-(g).
- **Hardening evidence (for P4):** unprivileged `nft` denied, service runs as `ids` with only CAP_NET_ADMIN, unit file at `os/petalinux/ids.service`, firewall rules in `/etc/nftables.conf` on the image.
- **Firewall evidence:** `results/firewall_blocked.png` (53 entries: 8 attackers + 45 benign, `timeout 1m`). On-device pack verification log: `pack OK: /opt/ids/pool-factory version 1 with 6 models`.
- **Design limitation text for the report (P1):** section 5, first bullet.
- **Reproduce:** mosquitto with `app/laptop/mosquitto.conf`, boot the image with `petalinux-boot --qemu --kernel`, run `replay.py --n 3000 --rate 300`; only one daemon on the broker.
- **paho 1.x patch:** PR #7 (`p2/paho1-compat`, `b9a26ad`) merged into `main` on 20 Nov 2026; the fix is in `main` and is now also in this branch after rebasing.
- **E3 results location:** branch `p2/e3-hardening-results`, commit `61ead56` at the time of writing (E3 CSVs, console log, firewall and read-only screenshots, the notes).
