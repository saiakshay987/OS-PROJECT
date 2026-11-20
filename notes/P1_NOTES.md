# P1 notes (hardware, HLS, kernel config)

Every command that worked, every error and its fix, with dates. Every number with the commit and command that produced it.

## 2026-11-20 results (base commit e3d4a03, models/pool = P3 pack v1, signed)

### Commands that worked
```
source .venv/bin/activate
for m in m0..m5: python hw/gen_hls.py models/pool/$m.npz hw/hls/build/$m
  (cd hw/hls/build/$m && g++ -O1 -o tb tb.cpp qmlp.cpp && ./tb)       # 564 vectors, 0 mismatches -> PASS (all six)
source /tools/Xilinx/Vitis_HLS/2024.1/settings64.sh
(cd hw/hls/build/$m && vitis-run --mode hls --tcl run_hls.tcl)         # csim PASS, csynth, IP export; ~40 s each
FOLD=fast python hw/gen_hls.py models/pool/$m.npz hw/hls/build_fast/$m # second design point (see below)
source /tools/Xilinx/Vivado/2024.1/settings64.sh
vivado -mode batch -source hw/build_bitstream.tcl -tclargs m0          # ~4 min, no errors
(cd hw/bit && sh ../make_bitbin.sh m0.bit)
```
Fix vs the guide's Tcl: the generator exports the IP as `qmlp_$m` (not `qmlp`), so the block-design line uses `xilinx.com:hls:qmlp_$m:1.0`. Also added utilisation and timing reports to the script.

### Six-model table (part xc7z020clg400-1, 10 ns target, default design point "base", HLS estimates)
| Model | Latency (cycles) | Clock est. (ns) | Time/record (us) | LUT | FF | DSP | BRAM18K |
|---|---|---|---|---|---|---|---|
| m0 | 291 | 6.912 | 2.011 | 12518 | 27377 | 0 | 1 |
| m1 | 290 | 6.912 | 2.004 | 12384 | 27290 | 0 | 1 |
| m2 | 226 | 6.982 | 1.578 | 10827 | 20908 | 0 | 1 |
| m3 | 193 | 6.991 | 1.349 | 10199 | 22878 | 0 | 1 |
| m4 | 5412 | 7.256 | 39.269 | 7445 | 14874 | 0 | 3 |
| m5 | 254 | 6.912 | 1.756 | 16690 | 39053 | 0 | 0 |
Zynq-7020 has 53200 LUT, 106400 FF, 220 DSP, 280 BRAM18K. Every model fits. DSP = 0 because 2-4 bit weights map to LUT logic.
Reports: hw/reports/m*_csynth.rpt.

### Two design points (generator option FOLD=fast: PIPELINE II=1 on each output-neuron loop + ARRAY_PARTITION complete)
Same answers (0 mismatches for all six). Only m4 changes; for m0-m3 and m5 Vitis HLS already pipelines/unrolls the loops by default, so the results are identical.
| m4 | Latency | Time/record | LUT | FF | BRAM18K |
|---|---|---|---|---|---|
| base | 5412 | 39.27 us | 7445 | 14874 | 3 |
| fast | 289 | 2.04 us | 15987 | 36318 | 1 |
So folding trades ~2.1x LUT for ~19x speed on m4. Reports: hw/reports/m*_fast_csynth.rpt.
NOTE: these are synthesis estimates; the post-route clock is not measured per model.

### Bitstream (m0, Vivado 2024.1, block design: PS7 + qmlp_m0 on M_AXI_GP0)
- m0.bit = 4,045,670 bytes; m0.bit.bin = 4,045,568 bytes (fixed size for this chip: swap time does not depend on the model).
- Post-implementation: 8296 LUT (15.6%), 9974 FF (9.4%), 0.5 BRAM tile. IP base address 0x4000_0000 (64K).
- Timing summary reports WNS +10.011 ns, WHS +0.012 ns, 0 failing endpoints. WNS larger than the clock period looks odd; I have not checked which clock the constraint sees, so treat it as "no violation reported" and not as a measured Fmax.
- Impl numbers are lower than HLS estimates (HLS 12518 LUT vs 8296 after optimisation).

### Swap-time estimate
size 4.05 MB / 128-145 MB/s = 28-32 ms floor (use 34 ms with overhead); 207 ms = Xilinx FPGA-manager log for the same chip (default SWAP_MS); ~550 ms = PYNQ forum report via the Python library. Sources must be cited in the report. Same for every model.

### Not done / untested
- Kernel fragment review against P2/P4 .config, timing-leak analysis (needs P2 jitter numbers).
- Nothing loaded on a board: register offsets, fpga_regs.py, dtbo, real swap time all untested.
- AXI-Lite input is deliberately slow; streaming interface is future work.

## 2026-11-20 kernel fragment findings (from P2/P4 messages and notes)
- P4's `os/buildroot/external/board/ids/linux-extra.cfg` shows `kernel/ids.cfg` lacked `CONFIG_NF_TABLES_IPV4` and `CONFIG_NFT_COUNTER`; both added to the fragment.
- P2: `ProtectHostname=` in the hardening drop-in has no effect on the PetaLinux kernel because `CONFIG_UTS_NS` is missing. Added `CONFIG_NAMESPACES=y` and `CONFIG_UTS_NS=y` to the fragment. NOT rebuilt: neither image has been confirmed to contain them.
- PetaLinux sizes (P2, QEMU, build 3): rootfs.cpio.gz 44,571,450 B; rootfs.ext4 194,957,312 B; image.ub 49,159,852 B; kernel 6.6.10-xilinx-v2024.1. P2 gave no before/after for the fragment, so no trimming effect can be claimed yet. Still needed: final `.config` from P2 and P4, and the grep check.

## Timing-leak analysis (estimate, not a measurement)
Signal: Vitis HLS latency of the six FPGA designs (table above). With the default design point the spread is m4 39.27 us vs m3 1.35 us = 37.9 us. With m4 built as `fast` all six lie between 1.35 and 2.04 us, a spread of 0.69 us. The default design point is therefore the leaky one, and it is leaky only because of m4.
Noise (P2, notes/P2_NOTES.md, QEMU service run at 300/s): alert latency median 21.4 ms, p95 195.0 ms. Laptop daemon with `arm` fallback: p50 3.5-5.6 ms, p95 4.1-7.3 ms. The signal is therefore about 1/560 (default) to 1/30,000 (fast) of the QEMU median.
Averaging N samples shrinks the standard error by sqrt(N). Crude sample count to tell two models apart (two-sample test, 5% two-sided, 80% power, N = 2 * 2.8^2 * sigma^2 / delta^2 per model), with sigma estimated as (p95 - median)/1.645:
| Noise | sigma | delta 37.9 us (default) | delta 0.69 us (fast) |
|---|---|---|---|
| QEMU service | ~106 ms | ~1.2e8 samples | ~3.7e11 samples |
| Laptop, arm | ~1.0 ms | ~1.2e4 samples | ~3.5e7 samples |
Assumptions that make these rough: sigma from percentiles assumes a normal shape, but the real tail is heavy (bursts of newly blocked sources, P2 E3-QEMU (f)); samples assumed independent; attacker assumed to see the full record-to-alert time.
Limits: (1) the demo runs the models as CPU integer code in QEMU, not on the FPGA, so the FPGA latencies are not what a client would observe; CPU inference time per model has not been measured. (2) HLS numbers are estimates, with AXI-Lite transfer time not included. (3) Must be re-measured from a second machine once the board exists. (4) A visible leak already exists in the swap itself: with the `hold` fallback, alert p95 rises to 206 ms at 500/s in QEMU (P2), so swap timing is observable with far fewer samples than model identity. (5) The blocked/allowed answers are an easier channel than timing (P4's E4).
Standard fix: delay every answer to the slowest model's latency. Cost: everyone gets the slowest model's speed, i.e. 39.27 us instead of 1.35 us at the default design point, but only 2.04 us if m4 is built `fast`. Building m4 `fast` removes most of the signal at no cost in speed, for about 2.1x m4's LUTs.

## 2026-11-20 evening: P2's kernel check and CPU model speed (source: P2 message, QEMU, emulated ARM)
### Kernel options on P2's PetaLinux build (kernel 6.6.10-xilinx, build/.../linux-xlnx-zc702-standard-build/.config)
| Option | Result |
|---|---|
| NF_TABLES, NF_TABLES_IPV4, OVERLAY_FS | =y (took effect) |
| FPGA | =y (FPGA_MGR has no line in 6.6.10; FPGA is the subsystem switch) |
| SOUND, DRM | not set (trimming took effect) |
| NAMESPACES, UTS_NS, NFT_COUNTER | NOT present: P2's build used the old `ids.cfg`; the new lines were only merged to main afterwards (PR #17). Not rebuilt, so unverified. |
Sizes (P2): zImage 4,560,016 B, vmlinux 13,468,952 B, image.ub 49,159,852 B. Boot 13.4 s before pruning, 9.6 s after, in QEMU. This is before/after pruning the *services*, NOT before/after the kernel fragment, so no fragment effect is claimed.
Buildroot (P4 notes): kernel 6.6.70-xilinx, uImage 4,659,952 B, boot to multi-user 29.5 s in QEMU. P4 also reports no UTS namespaces. No final Buildroot .config is in the repo (only `ids_zynq_defconfig`, which merges `kernel/ids.cfg` and `linux-extra.cfg`), and no before/after for the fragment. Still owed by P4: the final `.config`.

### CPU inference time per record in QEMU (us, median / p95; ids service stopped)
| Model | Batch 1 | Batch 64 | Batch 1024 |
|---|---|---|---|
| m0 | 768.0 / 894.9 | 44.4 / 47.7 | 64.4 / 71.3 |
| m1 | 778.1 / 920.9 | 46.0 / 49.3 | 65.8 / 75.3 |
| m2 | 767.7 / 933.2 | 35.9 / 38.9 | 46.4 / 47.5 |
| m3 | 753.6 / 895.4 | 24.0 / 26.9 | 20.2 / 20.9 |
| m4 | 788.8 / 930.6 | 54.4 / 57.9 | 77.2 / 91.4 |
| m5 | 1187.2 / 1399.3 | 44.3 / 47.8 | 34.3 / 35.3 |
P2: repeat runs differ by 15-18% at batch 1, so differences under ~15% mean nothing; batch 1024 p95 rests on only 50 calls.

### Timing-leak analysis, update with CPU numbers
- On the CPU the ranking differs from the FPGA ranking: at batch 1 the outlier is **m5** (about 1187 us, 400-430 us slower than the rest), the other five lie within 35 us (inside the 15% noise); at batch 1024 the spread is m3 20 us to m4 77 us. On the FPGA (default design) the outlier is m4 (39 us). So which model is distinguishable depends on the backend and the batch size.
- m5 vs the rest at batch 1: signal ~400-430 us against QEMU service noise (median 21.4 ms, p95 195 ms, sigma ~106 ms by the percentile rule): N = 2 * 2.8^2 * sigma^2 / delta^2 ≈ 0.9-1.1e6 samples per model. Blocking a source after its first alert would limit how many samples the attacker gets, but this was not measured.
- The five similar models would need ~1.4e8 samples (35 us signal), but that signal is below P2's measurement noise, so treat it as not measured.
- Caveat: the speed benchmark times the model call alone; the alert latency is the full QEMU path. Combining them assumes the noise is independent of the model, which was not tested. The sigma estimate assumes a normal shape although P2 shows a heavy tail.
- The pad-to-slowest fix would cost ~1.2 ms (m5, batch 1) per record on the CPU backend, ~39 us on FPGA (default design) or ~2 us if m4 is built fast.
