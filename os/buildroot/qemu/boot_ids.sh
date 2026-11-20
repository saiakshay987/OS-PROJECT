#!/usr/bin/env bash
# Boot the Buildroot IDS image in QEMU (emulated Zynq, NOT the board).  Repo copy of ~/boot_ids.sh (P4).
#   usage:  os/buildroot/qemu/boot_ids.sh            (O=$HOME/br-ids by default; O=/path/to/output to override)
# Leave QEMU with Ctrl-a x. The guest sees the laptop as 10.0.2.2 (QEMU user-mode network).
# Differences from a real board: QEMU's Ethernet PHY is at MDIO address 7 (the ZedBoard DTS says 0), so a QEMU-only DTB is made
# here from the real one; the real DTB (images/zynq-zed.dtb) is never changed.  1 vCPU, 512 MB, 256 MB SD copy (the image is not modified).
set -euo pipefail
O=${O:-$HOME/br-ids}
TMP=${TMPDIR:-/tmp}
if [ ! -f "$O/images/zynq-zed-qemu.dtb" ]; then
  "$O/host/bin/dtc" -I dtb -O dts -o "$TMP/zed.dts" "$O/images/zynq-zed.dtb" 2>/dev/null
  sed -i '/ethernet-phy@0 {/,/};/ s/reg = <0x00>;/reg = <0x07>;/; s/ethernet-phy@0 {/ethernet-phy@7 {/' "$TMP/zed.dts"
  "$O/host/bin/dtc" -I dts -O dtb -o "$O/images/zynq-zed-qemu.dtb" "$TMP/zed.dts" 2>/dev/null
fi
cp "$O/images/sdcard.img" "$TMP/sd.img"                 # fresh copy = fresh boot state every time
qemu-img resize -f raw "$TMP/sd.img" 256M >/dev/null
exec qemu-system-arm -M xilinx-zynq-a9 -m 512 -display none -serial null -serial mon:stdio \
  -kernel "$O/images/uImage" -dtb "$O/images/zynq-zed-qemu.dtb" \
  -drive file="$TMP/sd.img",if=sd,format=raw -nic user \
  -append "console=ttyPS0,115200 root=/dev/mmcblk0p2 ro rootwait"
