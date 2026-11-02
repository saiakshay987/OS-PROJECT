# Vaani-OS

*Vaani* (वाणी) means "voice / speech". **Vaani-OS** is a minimal, application-specific Linux distribution for the
PYNQ board (Zynq-7020) that turns spoken commands into laptop actions. OS-course project, Track E
(sensors + FPGA + ML inference).

```
  USB mic
     |
     v
+--------------------- PYNQ board (our custom Linux) ----------------------+
|  ARM : arecord (snd-usb-audio), 16 kHz mono; every 0.5 s take the        |
|        last 1 s and cut it into 49 frames x 512 samples                  |
|          |  AXI DMA (one transfer per window)                            |
|          v                                                               |
|  FPGA: Hann -> 512-pt FFT -> |X|^2 -> 40 mel energies                    |
|        + ALWAYS-ON VAD: speech-band energy vs adaptive noise floor       |
|          |  AXI DMA (mel)  +  gate decision in AXI-Lite registers        |
|          v                                                               |
|  ARM : gate open?  yes -> ln(mel + 1e-6) -> publish 'pynq/features'      |
|                    no  -> send nothing (heartbeat 'pynq/status' / 5 s)   |
|  systemd service | read-only root + overlay | nftables | SSH keys        |
+--------------------------------------------------------------------------+
     |  Ethernet, MQTT 1883 -- feature traffic ONLY while someone speaks
     v
+--------------------------- Laptop (RTX 4050) ----------------------------+
|  Mosquitto -> infer_server.py: CMVN -> CNN (ONNX Runtime, CUDA)          |
|  -> smoothing (reset on gaps) -> confidence threshold -> pyautogui       |
+--------------------------------------------------------------------------+
```

The FPGA computes speech features (FFT, mel filterbank) and runs an always-on voice-activity detector (VAD) that
gates the pipeline. During silence nothing is sent and the laptop GPU does no work. With a USB mic the ARM
still captures the audio, so say "FPGA does the DSP and the gating", not "the board sleeps".

## Interface contract (frozen after Day 1)

| Item | Agreed value (do not change without telling everyone) |
|---|---|
| Audio in | 16 000 Hz, mono, signed 16-bit little-endian (ALSA format S16_LE) |
| Analysis window | 1.0 s of audio (16 000 samples), a new window every 0.5 s |
| Frame | 512 samples (32 ms), hop 320 samples (20 ms) → 49 frames per window |
| Window function | Hann, 512 points (periodic), applied before the FFT |
| FFT | 512-point real FFT; keep bins 0…256 (257 bins); power = re² + im² |
| Mel filterbank | 40 triangular filters, 20 Hz – 8000 Hz, HTK mel formula. Weights generated ONLY by common/features.py |
| Feature | ln(mel_energy + 1e-6) → matrix 49 × 40 float32, row-major [frame][mel] |
| Normalisation | Done on the laptop only: subtract per-window mean of each mel band (CMVN). The board never normalises. |
| MQTT broker | On P3's laptop, 192.168.2.1:1883. Board is 192.168.2.99/24 (direct Ethernet cable). |
| VAD (voice activity detection) | Per frame: energy = ln(sum of mel bands 4…31 (≈ 280 Hz – 4.3 kHz) + 1e-6). A frame is speech if it is ≥ 9 dB above an adaptive noise floor. A window is speech if ≥ 5 of its 49 frames are. The gate stays open 1 extra window (hangover). ~2 s of continuous loudness re-anchors the floor (a fan turned on is not speech). Exact algorithm and constants = the Vad class in common/features.py; the FPGA block and the ARM fallback must both match it. |
| Topic pynq/features | Published only while the VAD gate is open (or always if VAD=off). Payload = 16-byte header, Python struct '&lt;QIHH': uint64 timestamp ms, uint32 window number, uint16 speech frames in window, uint16 flags (bit0 gate open, bit1 VAD computed in FPGA, bit2 VAD bypassed) + 49×40 float32 = 7 856 bytes |
| Topic pynq/status | JSON heartbeat every 5 s: uptime, backend (fpga/arm), vad (on/off), noise_floor_db, windows, published, proc_ms_avg, cpu_pct |
| Topic laptop/command | JSON: {"word": "up", "conf": 0.93, "ts": &lt;echoed timestamp&gt;} |
| Board settings | Defaults in /etc/voice/voice.conf (read-only image); overrides in /data/voice.conf (writable partition): BACKEND=fpga/arm, VAD=on/off, VAD_MARGIN_DB, MIC_DEVICE, BROKER, MQTT_USER, MQTT_PASS |
| Words (10 + 2) | up, down, left, right, stop, go, yes, no, on, off + _silence_ + _unknown_ |

`common/features.py` is the single source of truth. Anything that computes features (FPGA, ARM fallback, model
training) must match it.

## Team and ownership

| Who | Branch prefix | Owns |
|---|---|---|
| P1 | `p1/` | `hw/`, `kernel/`, `app/board/dma_lib.py`, `app/board/dma_test.py` |
| P2 | `p2/` | `os/petalinux/`, `app/board/frontend.py`, `app/board/voice.conf` |
| P3 | `p3/` | `common/`, `ml/`, `app/laptop/` |
| P4 | `p4/` | `os/buildroot/`, `security/`, `bench/`, `report/` |

Full per-person guides (PDF) are in `docs/guides/`.

## Layout

| Path | What | Status |
|---|---|---|
| `common/` | `features.py` (features + `Vad`), `mel_fb.h` for HLS, VAD test recording + expected gate | tested |
| `app/board/frontend.py` | mic -> features + VAD (FPGA or ARM) -> gated MQTT | tested with `BACKEND=arm` |
| `app/board/dma_lib.py` | FPGA backend that `frontend.py` calls | **untested sketch**, register offsets are placeholders |
| `app/laptop/` | `infer_server.py` (ONNX Runtime + MQTT), `actions.py`, `sim_board.py` | server tested; actions/sim use real devices |
| `bench/count_traffic.py` | counts MQTT messages/bytes for the VAD on/off matrix | tested |
| `hw/`, `kernel/` | HLS sketch, DT overlay, kernel config fragment | **untested**, needs Vivado and the board |
| `os/petalinux/`, `os/buildroot/` | image recipes, service, rules | **untested**, needs the board |
| `security/` | nftables, sshd, systemd and sysctl hardening | **untested** |
| `ml/` | model definition, recording script | model not trained yet |

## Quick start (any laptop, no board needed)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-laptop.txt
pytest -q                      # checks features + VAD against common/test_wavs/vad_expected.csv
```

Run the board program on a laptop with the ARM backend (the same code that runs on the board):

```bash
cd app/board
BACKEND=arm BROKER=127.0.0.1 MIC_DEVICE=default python frontend.py --backend arm
```

## Calendar (Day 1 = Sun 1 Nov 2026)

| Day | Date | Milestone |
|---|---|---|
| 1 | Sun 1 Nov | Contract + repo agreed (30 min call). All long installs started tonight. |
| 2–3 | 2–3 Nov | features.py with the Vad class + test vectors published (P3). QEMU images boot (P2, P4). FFT design simulates (P1). Model v1 trained (P3). Stock image measured offline (P4). |
| ~3–5 | board arrives | First hour: flash stock PYNQ image, run baseline benchmarks, check USB mic with arecord -l. |
| 6 | 6 Nov | Custom PetaLinux image boots on the board. Bitstream loads from Linux via FPGA manager. |
| 7 | 7 Nov | GO / NO-GO: custom image boots + bitstream loads + DMA loopback works? If not → fallback plan (below). |
| 8–9 | 8–9 Nov | End-to-end v1: speak → board → MQTT → laptop action. FFT on FPGA; mel + VAD on the ARM (features.py), so silence already produces no traffic. |
| 10–11 | 10–11 Nov | v2: mel filterbank and the always-on VAD moved into the FPGA (HLS). VAD margin tuned on our recordings. Kernel trimmed. Read-only root + hardening merged. |
| 12 | 12 Nov | Benchmarks: stock vs PetaLinux vs Buildroot; FPGA vs ARM backend; VAD on vs off (traffic, CPU, GPU calls during silence). Accuracy + latency. |
| 13 | 13 Nov | Feature freeze. Only bug fixes from here. |
| 14 | 14 Nov | Report, licence list, demo video recorded. |
| 15 | 15 Nov | Rehearsal, final tag v1.0, submission. |

Workflow rules are in [CONTRIBUTING.md](CONTRIBUTING.md).
