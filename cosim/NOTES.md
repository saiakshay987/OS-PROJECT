# QEMU + RTL co-simulation of the m0 IP: working notes

Branch `cosim/zynq-qemu`. No passwords are recorded here.

## Status

| Step | State |
|------|-------|
| 0 setup | done |
| 1 m0 RTL + register map | BLOCKED: Vitis HLS 2024.1 not found on this laptop (C++ side done) |
| 2 co-sim device tree | see below |
| 3 Check A (zynq_demo) | PASS (see below) |
| 4 Check R, 5 SystemC, 6 Check B, 7 Check C | not started (need RTL from step 1) |

## Setup facts (Step 0)

- Repo `~/Desktop/OS-PROJECT`, remote `saiakshay987/OS-PROJECT`, branched from `origin/main` (07badc4).
  The branch's upstream was unset on purpose so a bare `git push` cannot hit `main`.
- PetaLinux project `~/plx/ids-os`, settings `~/petalinux/2024.1/settings.sh`.
- Demo backup `~/ids-demo-images-BACKUP` (boot files, zImage, rootfs.cpio.gz, system.dtb, system.bit,
  u-boot, plus `system-user.dtsi.orig` and `device-tree.bbappend.orig`). Verified with `ls -la`.
  Live `images/linux/system.dtb` and the backup have the same md5 (bb50a00f...) before any change.
- Tool versions: verilator 4.038, tmux 3.2a, gtkwave present, SystemC headers at `/usr/include/systemc.h`.
  `dtc` is NOT on the default PATH; the only copy is in the PetaLinux sysroot
  (`~/petalinux/2024.1/sysroots/x86_64-petalinux-linux/usr/bin/dtc`), on PATH after sourcing `settings.sh`.
- `~/qemu-devicetrees` at tag `xilinx_v2024.1` (commit b9c88cb).
- Model pack `models/pool`: m0..m5.npz, canary.npz, manifest.json, manifest.sig all present.
- Vitis HLS: no `settings64.sh`, `vitis_hls` or `vitis-run` anywhere on this disk (searched `/`, PATH, history).
  P2 confirmed it is not installed on this laptop.

## Step 1 (partial)

```bash
source .venv/bin/activate
python hw/gen_hls.py models/pool/m0.npz hw/hls/build/m0
(cd hw/hls/build/m0 && g++ -O1 -o tb tb.cpp qmlp.cpp && ./tb)
```

Result: `564 vectors, 0 mismatches -> PASS` (C++ model matches the Python reference).
The Verilog step (`vitis-run --mode hls --tcl run_hls.tcl`) was not possible.

## Step 2: co-sim device tree

Project was unmodified beforehand (checked against the `.orig` backups). Applied: copied
`zynq-pl-remoteport.dtsi` into `device-tree/files/`, appended `/include/ "zynq-pl-remoteport.dtsi"` to
`system-user.dtsi`, added `file://zynq-pl-remoteport.dtsi` to `SRC_URI:append` in `device-tree.bbappend`;
`petalinux-build -c device-tree` succeeded. Output saved as `cosim/system-cosim.dtb` (decompiled: node
`cosim@0`, compatible `remote-port`, `chrdev-id = "pl-rp"`).

Forwarding: `m_axi_gp0` has `reg = <0x40000000 0x40000000>` -> remote-port channel 7, so 0x40000000-0x7FFFFFFF
reaches SystemC and **0x43C00000 is covered**. `m_axi_gp1` (0x80000000, 0x40000000) is channel 8.

Restore: the two source files were restored from `~/ids-demo-images-BACKUP/*.orig`, the extra dtsi removed, the
device tree rebuilt. `images/linux/system.dtb` md5 is again bb50a00f... (identical to the backup) and the
decompiled DTS diff is empty.
Normal-image boot check (2026-11-21): `petalinux-boot qemu --kernel` with the original `system.dtb` reached the login prompt; P2 logged in and confirmed the `ids` service is active.


## Step 3: Check A (stock `zynq_demo`)

Build: `git clone https://github.com/Xilinx/systemctlm-cosim-demo` (+ `git submodule update --init libsystemctlm-soc`,
submodule 99a0b66), then `.config.mk` containing
```
SYSTEMC_INCLUDE=/usr/include
SYSTEMC_LIBDIR=/usr/lib/x86_64-linux-gnu
```
and `make -j8 zynq_demo` (apt SystemC works, no source build needed; the Makefile reads `SYSTEMC_INCLUDE`/`SYSTEMC_LIBDIR`).

Run (two tmux sessions):
```bash
rm -rf /tmp/cosim && mkdir -p /tmp/cosim
# qemu session
cd ~/plx/ids-os && source ~/petalinux/2024.1/settings.sh
petalinux-boot qemu --kernel --dtb ~/cosim/system-cosim.dtb --qemu-args "-machine-path /tmp/cosim -icount 7 -sync-quantum 100000"
# sysc session (QEMU creates the socket and waits)
cd ~/cosim/run && ~/systemctlm-cosim-demo/zynq_demo unix:/tmp/cosim/qemu-rport-_cosim@0 100000
```
- Socket: `/tmp/cosim/qemu-rport-_cosim@0`. Sync-quantum 100000 on both sides, `-icount 7` (the table values worked first time).
- Versions: QEMU 8.1.0 (PetaLinux 2024.1, `qemu-system-aarch64 -M arm-generic-fdt-7series`), SystemC 2.3.3 (apt libsystemc 2.3.3-5.1).
- `petalinux-boot --qemu` is deprecated; `petalinux-boot qemu --kernel --dtb ...` is the form used. `--dtb` was accepted.
- Guest: `/dev/mem` is `crw-r----- root:kmem`, `/sbin/devmem` exists, so `sudo devmem` works (no kernel change needed).
- Working address: `0x40000000` (debugdev, `ADDRMODE_RELATIVE`, offset 0 = simulated time in ns, 32-bit).
  `sudo devmem 0x40000000 32` returned 0x72F6D3C3, then 0x9525338B, 0x24185ED3 on later reads. The values change
  between reads, so SystemC is answering; the last one is lower because the 32-bit ns counter wrapped
  (4.29 s of simulated time) while sudo/shell ran under `-icount 7`.
- Logs: `cosim/logs/checkA.txt`.
