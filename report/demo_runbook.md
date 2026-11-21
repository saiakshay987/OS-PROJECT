# Demo runbook and rehearsal checklist (deliverable 5)

P4, 21 Nov 2026. The demo runs the **Buildroot image in QEMU** (emulated Zynq-7000, one vCPU, 512 MB). There is no board: the
model runs as integer code on the ARM CPU and each swap *imitates* an FPGA load (`SWAP_MS` 207). Say this in the first sentence.
Every expected output below comes from a run on this laptop, with the file named next to it; nothing is estimated.

## 0. Known demo risks (read first)
| Risk | Evidence | What to do |
|---|---|---|
| `attack_demo.py` does **not** give the intended result on this image. With `ROTATE=off` it reported "EVASION found after 24-27 probes" and then "got through 1 (3%), blocked 30" (seeds 2 and 5); other seeds found no evasion. A copy with a 0.5 s alert wait (instead of 80 ms) found no evasion for seed 2. Most likely the 80 ms wait is shorter than the emulated guest's alert latency, so a late alert looks like an evasion (not proven). | `results/demo_rehearsal_buildroot_qemu.txt` | **Do not run `attack_demo.py` live.** Show the E2 table (`results/e2_rotation.csv`) instead, and say the live attacker demo needs a longer wait window. TODO(P3): make the wait a `--wait` option and re-test. |
| Counters are cumulative since the daemon started; the `uptime` field of `ids/status` is unreliable (the guest clock steps forward), do not quote it. | the counters are the `st` dict in `app/appliance/idsd.py`, which starts at zero with the daemon; P2 notes | Reboot the guest (new `boot_ids.sh` run) before any run whose numbers you will quote. Read the counters from `ids/status`, not from the replay's last printed line (P2 saw a stale `verdicts 0` there; `notes/P2_NOTES.md`). |
| Records are lost if the guest is overloaded: 200 records/s with stage 2 processed only about 1,340-1,580 of 3,000, so the recall of those runs (0.38-0.43) is not a detector result. | team message, not in a file; the clean 200/s run without stage 2 is `results/live_chain_buildroot_qemu.txt` | Use `--rate 50`. Check `recs` equals the number sent before quoting recall. |
| First-alert blocking blocks most benign hosts too (52 blocks in the clean 50/s run; the attacker/benign split of those was not captured. The earlier 200/s run had 8 attacker and 30 benign addresses). | `results/live_chain_buildroot_qemu_50.txt`, `results/live_chain_buildroot_qemu.txt`, `notes/P2_NOTES.md` section 5 | Say it is a design limitation, not a bug. |
| Boot time varies: 29.5 s and 56.8 s for the same image on this laptop. | `results/image_buildroot_qemu.csv`, `results/live_chain_buildroot_qemu_50.txt` | Boot the guest at least 2 minutes before the slot, never during it. |
| 3 restarts of `ids` within 300 s put the unit in the failed state (`StartLimitBurst=3`). | `os/buildroot/external/board/ids/post-build.sh` | Restart at most twice; recover with `systemctl reset-failed ids; systemctl start ids`. |
| Stage 2 needs `torch` and `models/stage2.pt` (not in git, P3's file). Neither exists on this laptop (P3's laptop has them and has already run stage 2 against the guest). | `ls models/stage2.pt` fails; `python -c "import torch"` fails in `.venv` | Run stage 2 on P3's laptop (GPU) or skip it (section 6). |
| MQTT has no authentication or TLS in the demo broker. | `app/laptop/mosquitto.conf` (`allow_anonymous true`) | Say so; `security/mqtt-auth.md` shows the fix. |

## 1. Prerequisites (T-15 min)
1. **Repo on branch `main` (or the tagged commit), clean:** `git status --short` prints nothing; `.venv/bin/python -m pytest -q` prints `5 passed`.
2. **Image built:** `ls -l ~/br-ids/images/sdcard.img ~/br-ids/images/uImage ~/br-ids/images/zynq-zed-qemu.dtb` (201,327,104 B / 4,677,360 B / 11,934 B on 20 Nov 22:27).
   If missing: `os/buildroot/build.sh build` (long; see `os/buildroot/README.md`).
3. **Broker IP (report-time).** Find the laptop's address when you arrive, it changes with Wi-Fi:
   `ip -4 -o addr show scope global`  (at 03:30 on 21 Nov this laptop had `10.29.21.145/24` on `wlp0s20f3`; do not reuse it).
   The **guest always reaches the broker at 10.0.2.2** (QEMU user-mode NAT), whatever the laptop's IP is. The laptop IP matters
   only if `replay.py` or `stage2_server.py` runs on a **second laptop**: then use `--broker <BROKER_IP>`.
4. **Mosquitto on the host, port 1883 open:**
   `mosquitto -c app/laptop/mosquitto.conf` (listens on `0.0.0.0:1883`, anonymous).
   Firewall: Fedora (firewalld; this laptop already has TCP/UDP 1025-65535 open in its zone, checked with `firewall-cmd --list-ports`):
   `sudo firewall-cmd --add-port=1883/tcp` (runtime only). Ubuntu (ufw, as P2 did): `sudo ufw allow 1883/tcp`.
   Check: `ss -ltn | grep 1883` shows `0.0.0.0:1883`.
   **Only one daemon may answer on the broker:** no `idsd.py` running on any laptop, and only one QEMU guest (`pgrep -a qemu`).
5. **Boot the guest (T-3 min):** `bash ~/boot_ids.sh` (repo copy: `os/buildroot/qemu/boot_ids.sh`). It copies `sdcard.img` fresh each time, so every boot
   starts with zeroed counters. Leave QEMU with **Ctrl-a x**. Login: `root`, no password on this QEMU console (stated limitation).
6. **Guest checks** (type in the guest console; expected output from `results/live_chain_buildroot_qemu_50.txt` and `results/demo_rehearsal_buildroot_qemu.txt`):
   | Command | Expected |
   |---|---|
   | `uname -r` | `6.6.70-xilinx` |
   | `mount \| grep ' / '` | `/dev/mmcblk0p2 on / type ext4 (ro,relatime)` |
   | `systemctl is-active ids nftables` | `active` twice (ids needs about 20-60 s after login in QEMU) |
   | `systemctl --failed --no-legend` | nothing |
   | `journalctl -u ids --no-pager \| tail -3` | `pack OK: /opt/ids/pool-factory version 1 with 6 models`, `idsd up: backend=arm input=mqtt rotate=poisson/30.0s pool=6 ...` |
   | `touch /etc/x` | `touch: cannot touch '/etc/x': Read-only file system` (stated by `notes/P4_NOTES.md`; message text from that note) |
7. **Counters at zero (host):** `mosquitto_sub -h 127.0.0.1 -t ids/status -C 1` shows `"recs": 0`. If not, reboot the guest.

## 2. Commands for the laptop side
Run from the repo root, with the venv: `source .venv/bin/activate` (or use `.venv/bin/python`).

| Step | Command | Notes |
|---|---|---|
| Stage 2 (P3's laptop with GPU, or any laptop with torch + `models/stage2.pt`) | `python app/laptop/stage2_server.py --broker 127.0.0.1` | Start it **from the repo root** (default `--model models/stage2.pt` is relative). Prints `stage 2 ready on cuda|cpu, classes: [...]`. If the broker is on another laptop use `--broker <BROKER_IP>`. |
| Replay (clean run) | `python app/laptop/replay.py --broker 127.0.0.1 --n 3000 --rate 50` | Takes 60 s plus 3 s. `--rate 50`, not 200: the guest is one emulated CPU. |
| Counters after the run | `mosquitto_sub -h 127.0.0.1 -t ids/status -C 1` | Wait 2 s after the replay ends (status is published every 2 s). Quote `recs`, `alerts`, `blocks`, `swaps`, `verdicts` from here. |
| Blocked set (guest) | `nft list set inet filter blocked` | Entries last 60 s; run it **during** the replay. |
| Stage-2 verdicts (guest) | `journalctl -u ids --no-pager \| grep -c VERDICT` | A **lower bound** (journald rotates). Prefer the `verdicts` field of `ids/status`. |

## 3. Expected output of the replay (clean 50/s run, `results/live_chain_buildroot_qemu_50.txt`)
```
sent 3000 records in 60.0 s (50/s), 1912 attacks
alerts 1710  TP 1666 FP 44 FN 246 TN 1044  recall 0.871  FPR 0.040
```
and `ids/status` after: `recs 3000, alerts 1710, blocks 52, swaps 7, fallback_recs 124, verdicts 0` (no stage 2 in that run).
Rotation is random, so expect small differences (recall about 0.87, FPR about 0.04). Two stage-2 runs at 50/s by P3 gave recall 0.769 and 0.827
(FPR 0.036, 0.043), reported in P3's replay output and not saved in a results file; the appliance counters were cumulative and not reset between them, so their processed fraction was never verified: do not quote them as detector results.
If recall comes out below about 0.85, first check `recs` against the 3,000 sent. Do **not** quote the replay's latency line.
With stage 2 running, `verdicts` should rise towards the number of alerts. Stage 2 **has** run against the Buildroot image (P3's laptop, 20-21 Nov, about 1,900 verdicts by the status counter) but without a reset of the counters; a clean stage-2 run on a freshly booted guest has not been recorded (TODO(P3, P4): commit P3's replay output; repeat once on a fresh guest). Stage-2 accuracy against the true labels has never been measured, so show the verdict names only as "the step runs".

## 4. Five-minute timed script
Pre-conditions done: guest booted and checked (section 1), broker up, stage 2 running if available, three terminals visible:
(A) QEMU console, (B) laptop shell, (C) slides open at the E2 table.

| Time | Who / where | Do | Show on screen / say |
|---|---|---|---|
| 0:00-0:30 | A | `mount \| grep ' / '`; `touch /etc/x`; `systemctl status ids --no-pager \| head -8` | Root is read-only; the service started by itself under systemd; hardening drop-ins listed. "No board: models run on the ARM CPU in QEMU; the swap load time is imitated." |
| 0:30-0:50 | A | `ps \| grep idsd`; `grep Cap /proc/<PID>/status` (PID from `ps`) | Runs as user `ids`; capability mask `0x1000` = CAP_NET_ADMIN only. **Not re-run in this session**: the values are from `notes/P4_NOTES.md`; check them in the rehearsal and drop the row if they differ. |
| 0:50-2:10 | B then A | B: `python app/laptop/replay.py --broker 127.0.0.1 --n 3000 --rate 50`. A (within 20 s of the start): `nft list set inet filter blocked` (repeat once) | Alerts and blocks start; the blocked set fills with 10.0.9.x (attackers) **and** 10.0.0.x (benign: the first-alert limitation). If stage 2 runs, show its console naming the attack types. |
| 2:10-2:50 | B | read the replay summary; `mosquitto_sub -h 127.0.0.1 -t ids/status -C 1` | Recall about 0.87, FPR about 0.04, `recs 3000`; "all numbers measured in QEMU, not on the board". |
| 2:50-3:30 | A | `journalctl -u ids --no-pager \| grep SWAP \| tail -5` | Model swaps at random times (`SWAP -> m3 (timer), blind window 207 ms, fallback=arm`): the moving target. (Optional faster rotation: `echo ROTATE=poisson > /data/ids.conf; echo ROTATE_S=5 >> /data/ids.conf; systemctl restart ids`, 1 of the 2 allowed restarts.) |
| 3:30-4:10 | C | E2 slide from `results/e2_rotation.csv`; one sentence on E4 (`results/e4_fingerprint_budget1000.csv`: 3 probes identify any of the 6 models) | Do **not** run `attack_demo.py` (section 0). |
| 4:10-4:45 | B | `cp -r models/pool /tmp/tp && cp /tmp/tp/m3.npz /tmp/tp/m2.npz && python3 common/modelpack.py verify /tmp/tp keys/pool_pub.pem` then `python3 common/modelpack.py verify models/pool keys/pool_pub.pem` | `REJECTED: m2.npz: hash mismatch`, then `OK: version 1, 6 models` (both outputs checked on this laptop, 21 Nov). This is the laptop-side check; the full tests T0-T6 are in `results/e5_update_tests.txt` (not run on the appliance). |
| 4:45-5:00 | - | Limitations slide | No board, serial root login without password, no secure boot, MQTT without TLS, `/data` is tmpfs, first-alert blocking. |

## 5. Rehearsal checklist (tick each; two timed runs, one person per step, a second person holding the video)
- [ ] `git status` clean on the demo branch; `pytest -q` = 5 passed; commit hash written on the first slide
- [ ] `~/br-ids/images/sdcard.img` present; guest boots; `systemctl --failed` empty
- [ ] Mosquitto listening on 0.0.0.0:1883; only one QEMU and no `idsd.py` on the laptop
- [ ] If a second laptop is used: its `--broker <BROKER_IP>` reaches the host (`mosquitto_sub -h <BROKER_IP> -t '#' -C 1` returns from there)
- [ ] Guest rebooted before the measured run; `ids/status` shows `recs 0`
- [ ] Replay at `--rate 50` finishes with `recs 3000` and recall near 0.87
- [ ] `nft list set inet filter blocked` shows both 10.0.9.x and 10.0.0.x during the run
- [ ] Stage 2 server up (or the skip decision made) and `verdicts` rises in `ids/status`
- [ ] Tamper check outputs match section 4; no private key on the demo laptop's screen (`keys_release/` stays off the projector)
- [ ] Timing: 2 runs <= 5:00; backup video opens and plays with sound off
- [ ] Slides open: E2 table, E4 sentence, limitations

## 6. Fallbacks
| Failure | Fallback |
|---|---|
| Wi-Fi/network down, second laptop unreachable | Everything except stage 2 runs on one laptop: broker, replay and QEMU on 127.0.0.1/10.0.2.2 need no network. Skip stage 2 and say verdicts are 0 because it runs on the GPU laptop. |
| Stage 2 server or `models/stage2.pt` missing | Skip it. State: "stage 2 runs on laptop B; shown in the recording (`results/live_chain_nft.png`, PetaLinux run, P2 notes)". |
| Guest does not boot or `ids` fails (`systemctl status ids` failed) | `systemctl reset-failed ids; systemctl start ids`; else show the recorded video and the committed files: `results/live_chain_buildroot_qemu_50.txt`, `results/image_buildroot_qemu.csv`, `results/read_only_root.png`. |
| Recall far below 0.85 | Check `recs`; reboot the guest and rerun once; if still low, show the committed run instead of the live one. |
| Anything else | Play the demo video (plan: "play the recorded video and show the committed CSVs"). |
