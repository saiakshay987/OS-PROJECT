# ids_cosim: m0 RTL behind QEMU's PL address space

`ids_cosim.cc` is Xilinx's `zynq_demo.cc` with one change: the demo's debug device is replaced by the
Verilated Vitis HLS RTL of m0 (`cosim/rtl`, top module `qmlp`) at **0x43C00000**, size 0x10000, reached
through `tlm2axilite_bridge<7, 32>` (relative address mode, same as the demo's debug device).
PL clock period 10 us (`QMLP_CLK_NS`), NOT the 100 MHz HLS target: with QEMU's 100 us sync quantum a 10 ns clock
makes the boot never finish. `ap_rst_n` is held low for 20 cycles, `interrupt` is unconnected.
A catch-all `memory` stub is mapped first at 0x41200000 (the image's AXI GPIO). `iconnect` sends every unmapped address to
target 0 at offset 0, so without the stub the GPIO driver's boot writes land on the IP's AP_CTRL (it then reads 0x81).
Tracing goes to `ids_cosim.vcd` and only covers rst_n and the AXI-Lite signals (a few KB). Do not trace the whole model or
the clock for a Linux boot (18 GB in ten minutes); `IDS_COSIM_VCD_CLK=1` adds the clock for short runs.

Note: the IP only decodes 7 address bits (0x00-0x7F). The bridge truncates wider addresses, so offsets
0x80-0xFFFF alias onto the register window. Only use 0x00-0x7F.

## Build

Prerequisites: Verilator 4.038, SystemC 2.3.3 (apt `libsystemc-dev`), and the demo built once:

```bash
git clone https://github.com/Xilinx/systemctlm-cosim-demo.git ~/systemctlm-cosim-demo
cd ~/systemctlm-cosim-demo && git submodule update --init libsystemctlm-soc
printf 'SYSTEMC_INCLUDE=/usr/include\nSYSTEMC_LIBDIR=/usr/lib/x86_64-linux-gnu\n' > .config.mk
make -j8 zynq_demo
```

Then, from this folder:

```bash
./build.sh ~/systemctlm-cosim-demo      # verilates ../rtl/*.v to obj_dir, compiles and links ./ids_cosim
```

`build.sh` takes the compile and link commands from `make -B -n zynq_demo` and swaps in our source.

## Run (two terminals / tmux sessions)

```bash
rm -rf /tmp/cosim && mkdir -p /tmp/cosim
# 1. QEMU with the co-sim device tree (it creates the socket and waits)
cd ~/plx/ids-os && source ~/petalinux/2024.1/settings.sh
petalinux-boot qemu --kernel --dtb <repo>/cosim/system-cosim.dtb \
    --qemu-args "-machine-path /tmp/cosim -icount 7 -sync-quantum 100000"
# 2. the SystemC side (same sync-quantum, in ns)
<repo>/cosim/sc/run.sh unix:/tmp/cosim/qemu-rport-_cosim@0 100000
```

In Linux: `sudo devmem 0x43C00000 32` should print a value with bit 2 (ap_idle) set.

## Waveform and debug signals

`ids_cosim.vcd` (written to the directory the program runs in, i.e. `cosim/rtl`) always contains `rst_n`, the AXI-Lite signals
and three debug signals copied out of the Verilated RTL: `ap_idle` (= `qmlp.ap_idle`), `ap_start` (= `ctrl_s_axi.int_ap_start`) and
`ap_done` (= `ap_CS_fsm[8]`, which is how `qmlp.v` defines it). They change only on real activity, so the file stays small.

The clock is recorded only when `IDS_COSIM_VCD_CLK=1`, and then only in a window that opens at the first AXI write and lasts
`IDS_COSIM_VCD_CLK_CYCLES` clock cycles (default 20000 = 0.2 s simulated, about 8 inferences). A whole Linux boot is about 1600 s
of simulated time, so dumping the clock all the time would be several GB. `cosim/demo/trim_vcd.py` cuts the first inference out of
the result. See `cosim/DEMO.md` for the full demo, expected output and the GTKWave signal list.
