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

Full plan and per-person guides: `docs/guides/`. Workflow rules: [CONTRIBUTING.md](CONTRIBUTING.md).
