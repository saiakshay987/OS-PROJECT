# hw/ (P1) — use Vivado / Vitis HLS 2024.1 only
- `gen_hls.py <model.npz> <out folder>` writes `qmlp.cpp`, `tb.cpp`, `vectors.txt`, `run_hls.tcl` for one pool member.
  Check first with plain g++ (`g++ -O1 -o tb tb.cpp qmlp.cpp && ./tb` must print PASS), then run Vitis HLS.
- Record per member in `notes/P1_NOTES.md`: latency (cycles and ns), LUT / FF / DSP / BRAM, achieved clock.
- `overlay/qmlp.dtso`, `make_bitbin.sh`, `../app/appliance/fpga_regs.py`: for the board; untested until it arrives.
- Commit: generator, Tcl, reports (`*.rpt`), `.xsa`, `.bit.bin` (about 4 MB each). Not the project folders.
