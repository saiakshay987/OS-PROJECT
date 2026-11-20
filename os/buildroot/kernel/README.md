# Buildroot kernel configuration (P4)

`linux-6.6.70-xilinx.config` is the **final kernel .config of the Buildroot image**, copied unchanged on 21 Nov 2026 from
`~/br-ids/build/linux-custom/.config` (file dated 20 Nov 21:51 IST, 137,347 B, sha256 `54b74ece...2575ef`).

| Item | Value | How to check |
|---|---|---|
| Buildroot | 2025.02.19 | `grep -m1 BR2_VERSION ~/buildroot/Makefile` |
| Kernel | Xilinx `linux-xlnx` tag `xlnx_rebase_v6.6_LTS_merge_6.6.70` (header: `# Linux/arm 6.6.70 Kernel Configuration`, `CONFIG_LOCALVERSION="-xilinx"`) | `head -3 linux-6.6.70-xilinx.config`; `BR2_LINUX_KERNEL_CUSTOM_TARBALL_LOCATION` in `../external/configs/ids_zynq_defconfig` |
| Base defconfig | `xilinx_zynq` (`BR2_LINUX_KERNEL_DEFCONFIG`) | defconfig |
| Fragments merged on top (in this order) | `kernel/ids.cfg` (P1) then `os/buildroot/external/board/ids/linux-extra.cfg` (P4) | `BR2_LINUX_KERNEL_CONFIG_FRAGMENT_FILES` in the defconfig |
| Image built from it | `uImage` 4,677,360 B, `vmlinux` 13,425,428 B, both written 20 Nov 21:55 IST (after the .config) | `ls -l ~/br-ids/images/uImage ~/br-ids/build/linux-custom/vmlinux` |

## What the fragments did (grep of this `.config`)
| Option | In the final .config |
|---|---|
| NF_TABLES, NF_TABLES_INET, NF_TABLES_IPV4, NFT_CT, NFT_LIMIT, NFT_REJECT, NF_CONNTRACK | `=y` |
| NFT_COUNTER | **no line**: the symbol does not exist in this kernel tree (`grep NFT_COUNTER net/netfilter/Kconfig` finds nothing), so that line of `ids.cfg` and `linux-extra.cfg` has no effect on 6.6.70 |
| OVERLAY_FS, STRICT_DEVMEM | `=y` |
| FPGA, FPGA_MGR_ZYNQ_FPGA, FPGA_BRIDGE, FPGA_REGION, OF_FPGA_REGION, OF_OVERLAY, OF_CONFIGFS, UIO, UIO_PDRV_GENIRQ | `=y` (board path; untested, no board) |
| NAMESPACES, UTS_NS | `=y` (added to `ids.cfg` on 20 Nov). The kernel behind the current `uImage` has them: `nm vmlinux` finds `utsns_operations`, and in the guest `ls /proc/self/ns` lists `uts` (checked 21 Nov, see `results/live_chain_buildroot_qemu_50.txt`). |
| SOUND, DRM, FB, MEDIA_SUPPORT, WLAN, BT, INPUT_JOYSTICK, INPUT_TOUCHSCREEN | `# ... is not set` |
| MODULES | `=y`, 10 options `=m`, 0 modules loaded in the guest (`modules` column of `results/image_buildroot_qemu.csv`) |

## Not available (needs P1)
No "before" kernel (same tree without the fragments) was built, so there is **no before/after size or boot time for the kernel
fragment**. The only before/after we hold is PetaLinux's, and that one is before/after pruning *services*, not the kernel
(`notes/P1_NOTES.md`, `notes/P2_NOTES.md`). To get one: `make O=<new dir> xilinx_zynq...` kernel-only build with the base
defconfig and compare `uImage` sizes (a kernel compile, about the length of one `make linux` run; not done).

PetaLinux kernel `.config` (6.6.10-xilinx, P2): **not committed**; it lives in `~/plx/ids-os/build/tmp/work/.../linux-xlnx-zc702-standard-build/.config` on P2's laptop. TODO(P2/P1): commit a copy.

Regenerate: `make -C ~/buildroot O=~/br-ids linux-rebuild` (after `ids_zynq_defconfig`), or run `../build.sh`.
