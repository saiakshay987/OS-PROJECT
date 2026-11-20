# ids_cosim: m0 RTL behind QEMU's PL address space

`ids_cosim.cc` is Xilinx's `zynq_demo.cc` with one change: the demo's debug device is replaced by the
Verilated Vitis HLS RTL of m0 (`cosim/rtl`, top module `qmlp`) at **0x43C00000**, size 0x10000, reached
through `tlm2axilite_bridge<7, 32>` (relative address mode, same as the demo's debug device).
Clock 100 MHz (`sc_clock` 10 ns, the HLS target), `ap_rst_n` held low for 20 cycles, `interrupt` unconnected.
Tracing goes to `ids_cosim.vcd` (AXI signals, clock, reset, plus the demo's own trace of the Zynq model).

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
