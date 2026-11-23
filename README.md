# os_project — a rotating-model intrusion-detection appliance

OS-course project (Track E): a minimal, hardened Linux distribution whose only job is to run a network
intrusion detector that **keeps changing its model**. A pool of small quantised neural networks classifies
connection records; the active model is swapped at random times so that whatever an attacker learns by
probing goes stale. Only signed, self-tested model packs are ever loaded.

```
 laptop A: flow exporter / attacker        appliance: custom Linux (QEMU now, PYNQ later)        laptop B: RTX 4050
 +-----------------------------+  61-byte  +--------------------------------------------+ alerts +-------------------+
 | replays UNSW-NB15 records   | --------> | active model (1 of 6, 2-4 bit) -> attack?  | -----> | stage 2: names    |
 | or probes with crafted ones |  records  | rotation: timer / random / on suspicion    | <----- | the attack type   |
 +-----------------------------+           | attack -> source address blocked (nftables)| verdict+-------------------+
                                           | packs: signed + canary self-test + rollback|
                                           +--------------------------------------------+
```

**Honest status.** There is no board yet, so the models run as integer code on the ARM CPU (QEMU) and each
swap *imitates* an FPGA bitstream load (`SWAP_MS`, default 207 ms). The FPGA version of each model is generated
and checked bit-for-bit in C simulation; loading it on real hardware is untested until the board arrives.

## Contract (frozen)

| Item | Value |
|---|---|
| Record | 61 unsigned bytes: 37 numeric features `round(255*min(1, log1p(v)/logmax))` + 24 one-hot bytes (0/255). Defined in `common/features.py` |
| Wire format | `<IIQ` header (sequence number, source IPv4, sender time in ms) + 61 bytes. Several records may be concatenated |
| Input | MQTT topic `net/flows` (default, works through QEMU NAT) or UDP port 5555 |
| Model | Integer MLP, arithmetic defined in `common/qmlp.py`. Attack if `score > thr` |
| Alert | topic `ids/alert`: `<IIQB` (seq, source, time, model index or 255 = fallback) + the 61 bytes |
| Verdict | topic `ids/verdict`: JSON `{seq, cat, conf, ts}` from the laptop |
| Status | topic `ids/status`: JSON every 2 s (active model, swaps, counters) |
| Model pack | folder with `m*.npz`, `canary.npz`, `manifest.json`, `manifest.sig` (ECDSA P-256 over the manifest) |
| Settings | `/etc/ids/ids.conf`, overridden by `/data/ids.conf` |

## Who owns what

| Who | Branch prefix | Folders |
|---|---|---|
| P1 | `p1/` | `hw/`, `kernel/`, `app/appliance/fpga_regs.py` |
| P2 | `p2/` | `os/petalinux/`, `app/appliance/idsd.py`, `app/appliance/ids.conf` |
| P3 | `p3/` | `common/`, `ml/`, `app/laptop/` |
| P4 | `p4/` | `os/buildroot/`, `security/`, `bench/`, `report/`, `ml/e4_fingerprint.py` |

## Quick start on any laptop (no board, no QEMU)

```bash
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                                                  # 5 tests

# data: put UNSW_NB15_training-set.csv and UNSW_NB15_testing-set.csv in data/unsw/   (see ml/README.md)
python ml/prepare.py data/unsw
python ml/train_pool.py                                    # pool + baseline + attacker surrogates -> models/
python common/modelpack.py keygen keys
python common/modelpack.py sign models/pool keys/pool_priv.pem 1
python ml/train_stage2.py

# four terminals:
mosquitto -c app/laptop/mosquitto.conf
python app/laptop/stage2_server.py --broker 127.0.0.1
python app/appliance/idsd.py --broker 127.0.0.1 --factory models/pool --pubkey keys/pool_pub.pem --pool /tmp/pool --block log --rotate fixed --rotate-s 5
python app/laptop/replay.py --broker 127.0.0.1 --n 5000 --rate 500

# experiments (from the repo root; CSVs land in results/):
python ml/e1_transfer.py ; python ml/e2_rotation.py ; python ml/e4_fingerprint.py
```
No dataset yet? `python ml/make_synth.py data/unsw 20000` writes a FAKE one for trying the code. Never report its numbers.

## What is tested

| Part | Status |
|---|---|
| `common/`, `ml/`, `app/`, `hw/gen_hls.py`, `bench/speed.py`, `tests/` | Run end to end on a laptop-class Linux machine with **fake data** |
| Real UNSW-NB15 results | Not produced yet: that is the team's job (Days 1-3) |
| Generated HLS C++ | Bit-exact against Python in g++; **not** yet run through Vitis HLS |
| `app/appliance/fpga_regs.py`, `hw/overlay/`, `FpgaBackend` | **Untested**, needs the board; register offsets are placeholders |
| `os/`, `kernel/`, `security/` files | **Untested** config written for PetaLinux 2024.1 / Buildroot; verify in QEMU |

## P2: appliance, hardening, E3, co-simulation

Owner: P2. Full notes with commands, errors, dates and commits: [notes/P2_NOTES.md](notes/P2_NOTES.md). The co-simulation has its own
notes and a demo guide: [cosim/NOTES.md](cosim/NOTES.md) and [cosim/DEMO.md](cosim/DEMO.md). This section supersedes the "untested" rows of
the table above for the P2 parts; the FPGA parts are still untested on a board.

**Label key.** *measured* = run on a laptop; *emulated in QEMU* = emulated ARM guest, counts are right, timing is not hardware speed;
*imitated* = a stand-in value; *not done* = not attempted or no result file.

### Boot the image in QEMU

PetaLinux 2024.1 (ZC702 BSP), kernel 6.6.10-xilinx, systemd. The root is an initramfs in RAM, mounted read-only; `/data` is a 64M tmpfs.
Recipes: `os/petalinux/` (copy `project-spec/meta-user/` into the PetaLinux project, see `os/petalinux/README.md`). The build output is not in the repo.

```sh
source <petalinux-install-dir>/settings.sh
cd ~/plx/ids-os && petalinux-build        # first full build 37m13s on 20 Nov 2026 (measured, notes section 4)
petalinux-boot --qemu --kernel            # leave QEMU with Ctrl-a x
```
Guest network is QEMU user-mode NAT: guest 10.0.2.15, the laptop is 10.0.2.2. The console is the only way in (sshd is masked). The lab login
is shared with the team directly, it is not in the repo. The `ids` service starts by itself (`User=ids`, `AmbientCapabilities=CAP_NET_ADMIN`,
`Restart=on-failure`); defaults are in `/etc/ids/ids.conf` (`app/appliance/ids.conf`), overrides in `/data/ids.conf`.

### Start the broker, replay, read the topics

```sh
# laptop; stop any system mosquitto first (it already holds port 1883): sudo systemctl stop mosquitto
mosquitto -c app/laptop/mosquitto.conf        # listener 1883
# second terminal, with the guest running (or a laptop idsd.py: only ONE daemon may answer on the broker at a time)
python3 app/laptop/replay.py --n 3000 --rate 300
```
`replay.py` prints sent, alerts, TP/FP/FN/TN, recall, FPR and the record-sent to alert-seen latency (median, p95). Add
`--csv results/x.csv --label name` to append a row. Topics (`mosquitto_sub -t '<topic>'` on the laptop):

| Topic | Content |
|---|---|
| `ids/alert` | binary: `<IIQB` (sequence, source IPv4, sender time in ms, pool member index that scored it, 255 = the fallback model during a swap) followed by the 61-byte record. One per flagged record |
| `ids/status` | JSON every 2 s: counters (`recs`, `alerts`, `blocks`, `swaps`, `fallback_recs`, `unclassified`, `held`, `verdicts`), `member`, `backend`, `rotate`, `pool`, `in_swap`, `uptime` |
| `ids/verdict` | JSON from stage 2 (`app/laptop/stage2_server.py`): `seq`, `cat` (attack type), `conf`, `ts`. The appliance logs each as a `VERDICT` line in its journal; trust the journal count, the replay's printed `verdicts` can be stale |

In the guest: `sudo nft list set inet filter blocked` (entries expire after 60 s), `sudo journalctl -u ids --no-pager | grep -c VERDICT`.

### Read the results

| File | What it is | Label |
|---|---|---|
| `results/e3_blind_window.csv` | E3, 28 rows: swap time (34/207/550 ms) x fallback (arm/hold/open) x rate (100/500/1500 per s), 30 s each, plus no-rotation. Columns: `label,sent,rate,attacks,tp,fp,fn,tn,recall,fpr,alert_ms_p50,alert_ms_p95,swaps,fallback_recs,unclassified,held,recs`. Latencies are record-sent to alert-seen, in ms | measured (laptop daemon); the swap time is imitated |
| `results/e3_qemu.csv` | the same columns, 14 rows, daemon in the QEMU guest. `swaps`, `fallback_recs`, `unclassified`, `held`, `recs` are **cumulative since daemon start**: subtract the previous row of the same daemon run (see notes section 4) | emulated in QEMU; swap time imitated |
| `results/e3_console.log` | console output of the laptop E3 run | measured |
| `results/image_petalinux_qemu.csv` | `bench/measure_image.sh` output, before and after hardening and pruning (`mem_used_mb` is really KB; `root_used_mb` meaningless on a RAM root) | emulated in QEMU |
| `results/firewall_blocked.png`, `firewall_blocked_hardened.png`, `read_only_root.png`, `live_chain_nft.png` | screenshots: blocked set, hardened service still adding rules, read-only root, live chain | emulated in QEMU |

### Real, imitated, not done

| Item | Status |
|---|---|
| Integer model, signed pack check, rotation, fallbacks, nft blocking, read-only root, masked units, service sandbox, live chain with stage 2 | **Real**, on the QEMU image (emulated ARM) |
| E3 on the laptop (x86), model code and daemon | **Real**, measured |
| Co-simulation of m0: Linux in QEMU drives the Verilated RTL of m0; 64/64 canary records matched; the waveform shows 284 busy cycles for one inference (`cosim/demo/one_inference.vcd`) | **Real as a simulation**. m0 only. The PL clock is set to 10 microseconds, so only cycle counts mean anything |
| FPGA model swap time `SWAP_MS` = 207 ms | **Imitated**: the daemon waits this long to stand in for loading a bitstream. Not measured on any board |
| `BACKEND=fpga`, bitstream loading, PS-PL transfer, real hardware latency | **Not done**: no board was used |
| Co-simulation of m1..m5, or of the daemon on `BACKEND=fpga` | **Not done** |
| Stage-2 accuracy against true labels | **Not done** (the verdicts show that the step runs, not how accurate it is) |
| Why the service is slower than a manual nft run; the setuid drop 17 -> 9 | **Not worked out** |

Known limitations, stated in the notes: first-alert blocking also blocks benign hosts (34 of 50 in the journal run); `ProtectHostname` has
no effect because the kernel has no namespaces; the guest clock is not synchronised, so guest dates are wrong.

Full plan and per-person guides: `docs/guides/`. Workflow rules: [CONTRIBUTING.md](CONTRIBUTING.md).
