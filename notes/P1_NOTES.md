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
