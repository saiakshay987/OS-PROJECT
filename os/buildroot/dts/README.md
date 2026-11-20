# Device trees used by the Buildroot image (P4)

| File | What | Status |
|---|---|---|
| `zynq-zed.dts`, `zynq-7000.dtsi` | Source from the kernel tree `arch/arm/boot/dts/xilinx/` (tag `xlnx_rebase_v6.6_LTS_merge_6.6.70`), `BR2_LINUX_KERNEL_INTREE_DTS_NAME="xilinx/zynq-zed"`. Board model "Avnet ZedBoard board". | Built into `images/zynq-zed.dtb`; boots in QEMU |
| `zynq-zed.dtb.decompiled.dts` | `dtc -I dtb -O dts` of `~/br-ids/images/zynq-zed.dtb` (sha256 `c8071c83...`). This is the DTB U-Boot/extlinux loads from the SD image. | As built |
| `zynq-zed-qemu.dtb.decompiled.dts`, `zynq-zed_vs_qemu.diff` | QEMU-only DTB (sha256 `229d7af0...`). The diff shows the **only** change: Ethernet PHY `ethernet-phy@0 reg=<0x00>` becomes `ethernet-phy@7 reg=<0x07>`, because QEMU's PHY answers at MDIO address 7. Made by `../qemu/boot_ids.sh`. | QEMU only; never used on a board |

**Gap: no PYNQ-Z2 device tree.** The target board is the PYNQ-Z2, but the Buildroot image uses the *ZedBoard* DTS (the
closest board in the Xilinx kernel tree that QEMU can emulate). It has never been booted on a PYNQ-Z2 and the PYNQ-Z2's
Ethernet PHY, clocks and PL connections are not described. TODO(P1/P4): write `zynq-pynq-z2.dts` when the board is available.

## Other device-tree files in the repo (not owned by P4)
| File | Owner | Status |
|---|---|---|
| `hw/overlay/qmlp.dtso` | P1 | "BOARD ONLY, untested" (its own header). Describes the accelerator at `0x40000000` as `generic-uio`; never loaded on a board. |
| `cosim/system-cosim.dtb` | P1/co-sim | PetaLinux ZC702 device tree with the remote-port node for QEMU+RTL co-simulation; used in the co-simulation checks recorded in `cosim/NOTES.md` (Checks A, B, C, R PASS). Not an appliance DT. |
| PetaLinux `system.dtb` / `system-user.dtsi` | P2 | **Not in the repo.** `os/petalinux/` has no device-tree recipe; the DTB lives in `~/plx/ids-os/images/linux/` on P2's laptop. TODO(P2). |
