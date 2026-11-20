# Size comparison: stock vs Buildroot vs PetaLinux (constraint c: at least 40% smaller)

Written 21 Nov 2026 (P4). Every number has the command and file it came from. Percentages were computed with `python3` from
the numbers in the tables. "Smaller" = `100 - 100 x ours / stock`.

**Verdict: the 40% constraint is met by a wide margin for the root filesystem** (Buildroot 97.9% smaller by `du`, 98.2% by `df`,
97.9% by archive size; PetaLinux 97.5% by archive size). The two kernel images are *not* comparable (see section 4), so no
kernel-size percentage is claimed against the 40% target.

## 1. What "stock" is
Stock = the PYNQ-Z2 v3.1.1 SD image `~/Downloads/pynq_z2_v3.1.1.img` (8,337,309,696 B), the distribution the Zynq board would
normally run (Ubuntu-based, 1,628 dpkg packages). It is the only stock baseline measured; it was measured offline (read-only loop
mount), not booted.

## 2. Like-for-like table (root filesystem content)

| # | Metric | Stock | Buildroot | PetaLinux | Reduction (Buildroot / PetaLinux) |
|---|---|---|---|---|---|
| A | **Used space of the root tree, `du -sx --block-size=1M`** (allocated blocks) | **5,440 MiB** | **114 MiB** (host copy of the target dir, 4 KiB blocks like the stock ext4) | not measurable (PetaLinux project is not on this laptop) | **97.9%** / n.a. |
| B | **In-guest style `df -m` used on the mounted root filesystem** | **5,440 MiB** | **96 MiB** (image has 1 KiB blocks) | n.a. (RAM root, `df` shows 0) | 98.2% / n.a. (see note 2) |
| C | **Uncompressed archive of the root tree** (tar / cpio) vs stock apparent size | 5,218,332,637 B (4,977 MiB, lower bound, note 3) | `rootfs.tar` 107,591,680 B (102.6 MiB) | `rootfs.cpio` 130,197,504 B (124.2 MiB) | 97.9% / 97.5% |
| D | Compressed archive | not measured | `rootfs.tar` gzipped: 36,689,725 B (35.0 MiB, `gzip -c rootfs.tar \| wc -c`) | `rootfs.cpio.gz` 44,571,450 B (42.5 MiB) | n.a. |
| E | Whole SD image file (includes free space) | 8,337,309,696 B | `sdcard.img` 201,327,104 B (192 MiB: 32 MiB boot + 160 MiB root, 38 MiB of it free) | no SD image (QEMU boots `image.ub`) | 97.6% / n.a. |
| F | Packages | 1,628 (`dpkg`) | 26 packages with files in the rootfs (29 non-virtual target packages incl. kernel, U-Boot, headers) | 229 (Yocto `rootfs.manifest`) | different counting methods, **not comparable** |

Rows A, B, C are the headline. A is the strictest like-for-like (same tool, same unit, same 4 KiB block rounding, same ext4 host
filesystem). C compares two byte-exact archives against the stock tree's apparent size and does not depend on block size.

### Commands and source files
| Number | Command | Where recorded |
|---|---|---|
| Stock 5,440 MiB (A) | `sudo du -sx --block-size=1M /mnt/stock_root` in `bench/stock_offline.sh` | `results/stock_offline.txt` (line `5440 /mnt/stock_root`), `notes/P4_NOTES.md` |
| Stock 5,440 MiB re-measured 21 Nov | loop-mounted read-only, `df -m` shows `5440` used of 7477; non-root `du -sx --block-size=1M` gives 5,437 (18 directories unreadable without root: 3 MiB less) | run now, console output |
| Stock apparent bytes (C) | non-root `du -sx --apparent-size -B1 <mount>` = 5,218,332,637 (same 18 directories skipped, so it is a lower bound; a lower stock number makes the reduction look smaller, i.e. conservative) | run now |
| Stock 1,628 packages / 14 setuid / 20 units | `grep -c '^Package:' .../dpkg/status`; `find -perm -4000`; `ls multi-user.target.wants` | `results/stock_offline.txt`, re-run now: 1628 / 14 / 20 |
| Buildroot 114 MiB (A) | `du -sx --block-size=1M ~/br-ids/target` (image built 20 Nov 22:27) | run now; `notes/P4_NOTES.md` |
| Buildroot 96 MiB (B) | `df -m` on the loop-mounted `~/br-ids/images/rootfs.ext2` = 96 used (also `du` = 96, apparent 95); in the guest `df -m /` gives 96 | run now; `results/image_buildroot_qemu.csv` (`root_used_mb` 96), `results/live_chain_buildroot_qemu_50.txt` |
| Buildroot tar, sd image, gzip (C, D, E) | `ls -l ~/br-ids/images/{rootfs.tar,sdcard.img}`; `gzip -c rootfs.tar \| wc -c` | run now |
| Buildroot 26 packages | `cut -d, -f1 ~/br-ids/build/packages-file-list.txt \| sort -u` gives 27 names; one of them (`toolchain`) is Buildroot's toolchain pseudo-package; the other 26 are the packages in `report/package_manifest_buildroot.csv` with `in_rootfs=yes` | run now |
| PetaLinux `rootfs.cpio` 130,197,504 B; `.cpio.gz` 44,571,450 B; `rootfs.ext4` 194,957,312 B; `image.ub` 49,159,852 B; 229 packages | `ls -l ~/plx/ids-os/images/linux` and `rootfs.manifest` on P2's laptop (build 3, 20 Nov 18:42) | `notes/P2_NOTES.md` section 4 table (lines for `rootfs.cpio`, `rootfs.cpio.gz`, `rootfs.ext4`) and section "Service design and packages". **Not re-measured here** (project not on this laptop). |

## 3. Notes on like-for-like
1. **Why A and B differ for Buildroot (114 vs 96 MiB).** The Buildroot image was built with 1 KiB filesystem blocks
   (`dumpe2fs -h rootfs.ext2`: block size 1024), which wastes less space on many small files than the 4 KiB blocks of the stock ext4
   (`stat -f` on the stock mount: 4096) and of the host directory. Row A (114 MiB) is the conservative number because it uses the
   same 4 KiB rounding as the stock. Row B (96 MiB) is what the board would really use.
2. Row B for stock is a host-side `df -m` of the mounted partition, the same quantity `measure_image.sh` prints inside a booted image
   (`df -m /`). The stock image was never booted, so no in-guest number exists for it.
3. **Stock apparent size is a lower bound** (unreadable directories skipped, no sudo available for the re-measurement). The
   root-run `du` in `bench/stock_offline.sh` (5,440) differs by only 3 MiB from the non-root one (5,437), so the effect is below 0.1%.

## 4. Not like-for-like (reported only so nobody mixes them)
| Pair | Why it cannot be used for the 40% claim |
|---|---|
| PetaLinux `rootfs.ext4` 194,957,312 B (185.9 MiB) vs stock 5,440 MiB | `rootfs.ext4` is a fixed-size filesystem **container** (free space included), not used bytes. Use `rootfs.cpio` (row C). |
| PetaLinux `image.ub` 49,159,852 B vs Buildroot `sdcard.img` | `image.ub` is a FIT bundle of kernel + device tree + the initramfs rootfs (the QEMU boot image); `sdcard.img` is a partitioned disk with a separate kernel. Different things. |
| Kernel: stock `image.ub` 7,147,780 B vs Buildroot `uImage` 4,677,360 B (34.6% smaller) | The stock file is a FIT image (`file`: "Device Tree Blob version 17", 7,147,780 B); its contents were not unpacked, so it is not known how much of it is kernel. The Buildroot `uImage` is the bare kernel (`mkimage -l`: "ARM Linux Kernel Image (uncompressed)", 4,677,296 B). Also the stock `BOOT.BIN` (1,165,852 B) vs ours (`boot.bin` 136,220 B + `u-boot.img` 1,326,116 B). The 34.6% is shown for information only and is **not** claimed as meeting the 40% target. |
| Package counts 1,628 / 229 / 26 | dpkg, Yocto `rootfs.manifest` and Buildroot `packages-file-list` count different things (stated by P2 in `notes/P2_NOTES.md`). |
| PetaLinux `rootfs.cpio` "about 130 MB" (a team message) | **Reconciled.** 130,197,504 B is the *uncompressed* `rootfs.cpio` (124.2 MiB, `notes/P2_NOTES.md` table). The compressed `rootfs.cpio.gz` is 44,571,450 B (42.5 MiB). Both figures are right; they are different files. Use 124.2 MiB (uncompressed) next to Buildroot's `rootfs.tar` 102.6 MiB, and 42.5 MiB for the compressed file. |

## 5. Buildroot vs PetaLinux, same kind of number
`rootfs.tar` 107,591,680 B (Buildroot) vs `rootfs.cpio` 130,197,504 B (PetaLinux): Buildroot's root is 17.4% smaller as an archive.
The PetaLinux figure is P2's, from build 3 (`notes/P2_NOTES.md`; not re-measured here). The two images contain different things
(229 Yocto packages vs 26 Buildroot packages), so this compares two finished images, not the build systems.

## 6. What is still missing
- TODO(P2): `du -sx --block-size=1M` of the PetaLinux rootfs (extract `rootfs.tar.gz` and run it) to complete row A for PetaLinux.
- TODO(P1): kernel size before/after the `ids.cfg` fragment (no "before" kernel was built for either image).
- Board numbers (RAM, boot) need the PYNQ-Z2.
