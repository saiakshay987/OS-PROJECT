# Clean-clone Buildroot build: reproducibility evidence

Run unattended overnight on 21 Nov 2026 (P4 branch `p4/clean-build-evidence`). Raw data: `results/clean_build_finish.txt`
(collected by `~/br-clean/finish.sh`); the full build log stays on the laptop at `~/br-clean-build.log` (39 MB, not committed).

## Verdict
**The image was rebuilt from a fresh clone of GitHub `main` with the documented script and it boots: yes.** One script bug was found
(in the `manifest` step, not in the image build), fixed in `os/buildroot/build.sh` on this branch and the step retried once successfully.
The result is **functionally identical but not bit-for-bit identical** to the earlier image in `~/br-ids`.

## What was run
| Item | Value |
|---|---|
| Source | `git clone https://github.com/saiakshay987/OS-PROJECT.git ~/clean-clone`, branch `main`, commit `64fa208` (merge of PR #25) |
| Build host | the same Fedora laptop, kernel 7.2.10-200.fc44, 12 CPUs, 7 GiB RAM, gcc 16.2.1, Python 3.14.8 |
| Command | `JOBS=$(nproc) BUILDROOT_DIR=$HOME/br-clean/buildroot OUT=$HOME/br-clean/out $HOME/clean-clone/os/buildroot/build.sh all`, run as `nohup systemd-inhibit --what=sleep:idle:handle-lid-switch nice -n 10 bash -c "$CMD"` (`~/br-clean/command.txt`) |
| Buildroot | 2025.02.19, **downloaded by `build.sh` itself** from `buildroot.org` into `~/br-clean/buildroot` (the directory did not exist before, so the script's download branch was exercised); its own `dl/` is inside `~/br-clean` (1.2 GB) |
| Start | 2026-11-21 04:24:02 IST |
| Image files complete | `sdcard.img` written 05:54 IST; log last written 05:54:34 IST |
| Duration | about 1 h 30 min (04:24:02 to 05:54:34), including the first `legal-info` |
| Exit | the image build finished normally; the `manifest` step then stopped with a Python `JSONDecodeError` (see "Script bug"), so `build.sh all` itself exited with an error at 05:54 |
| Host free space on `/` | before 30,294 MiB; after the build 15,597 MiB (a 14.7 GiB build tree: `du -sh ~/br-clean` 15 GB) |
| Safety nets | disk watchdog (abort below 3 GB free) and a 10:00 IST time box; neither triggered |

## Script bug found and fixed (documentation/script bug)
`build.sh manifest` ran `make -C <buildroot> ... show-info > show-info.json`. With `-C`, make prints `make: Entering directory ...` to stdout, which ended up as
the first line of the JSON, so `gen_manifest.py` failed with `JSONDecodeError: Expecting value: line 1 column 1` (log lines 137110-137126). My earlier manual run did not
use `-C` and did not see it. Fix (this branch, `os/buildroot/build.sh`): `--no-print-directory` on the `show-info` call. Retry (once, `manifest` step only, 22.7 s): success; the regenerated
`report/package_manifest_buildroot.csv` and `report/licences-manifest.csv` are **identical** to the committed files (`git diff` in the clone shows only the `build.sh` change).
The failed first attempt had overwritten the clone's `package_manifest_buildroot.csv` with an empty file; that is a side effect of the shell redirect and was only in the clone.

## Comparison with the earlier image (`~/br-ids`, built 20 Nov 22:27)
| Check | New (clean clone) | Earlier | Result |
|---|---|---|---|
| `sdcard.img` size | 201,327,104 B | 201,327,104 B | same |
| `uImage` size | 4,677,360 B | 4,677,360 B | same |
| `vmlinux` size | 13,425,428 B | 13,425,428 B | same |
| `rootfs.tar` size | 107,591,680 B | 107,591,680 B | same |
| `rootfs.ext2` size | 167,772,160 B | 167,772,160 B | same |
| `du -sx --block-size=1M target` | 114 | 114 | same |
| `zynq-zed.dtb` sha256 | `c8071c83efed…aff28` | `c8071c83efed…aff28` | **identical** |
| `.config` (comments and path/version lines ignored) | | | **no difference** |
| Kernel `.config` vs `~/br-ids` and vs `os/buildroot/kernel/linux-6.6.70-xilinx.config` | | | **no difference** |
| Package names with files in the target (`packages-file-list.txt`) | 27 | 27 | no difference |
| `sdcard.img` sha256 | `36976e2b…75cf8` | `57612144…73c43` | **different** |
| `uImage` sha256 | `ccf7ed1d…29d3` | `d47c1482…468e3` | **different** |
| `rootfs.tar` sha256 | `62f4308b…2f389` | `365c78d7…a057f` | **different** |
| `zImage`, `vmlinux` sha256 | | | different (same sizes) |

**Why the hashes differ (partly explained, not fully isolated).** Comparing the two `rootfs.tar` file by file (5,206 entries each, same names): 548 regular files differ.
524 are Python `.pyc` files (same size, different bytes), 20 are ELF binaries (e.g. `busybox`, `dbus-*`, `libcrypto.so.3`, `libnftables.so.1.1.0`), and 4 other files.
7 differ in size: `opt/ids/fpga_regs.py` (1,254 B vs 1,050 B), `libstdc++.so.6.0.32-gdb.py`, `_sysconfigdata__linux_arm-linux-gnueabihf.pyc`, `config-3.12-…/Makefile`,
numpy `__config__.pyc` (two copies) and `udev/hwdb.bin`. The `fpga_regs.py` difference **is a real source difference**: P1 changed that file in commit `3a27fb9` (21 Nov 01:39), after the earlier
image was built. The others are consistent with embedded build paths (`~/br-clean` vs `~/br-ids`, a different path length) and build timestamps; the cause of each was **not** analysed. So the build is
reproducible in content and size but not bit-for-bit.

## Boot of the new image (measured in QEMU (emulated ARM), not on the board)
Same options as `~/boot_ids.sh` through the repo script `os/buildroot/qemu/boot_ids.sh` with `O=~/br-clean/out`, `TMPDIR=~/br-clean/tmp`, headless, `timeout 180`, serial to a file
(`results/clean_build_finish.txt`):
- login prompt reached (`ids login:`) and `Started Rotating-model intrusion detector.` on the console; QEMU stopped by the timeout (status 124, expected).
- The console log does not contain "pack OK" (that line is journald output, not console output), so a **second** headless boot logged in as root and read the journal:
  `uname -r` 6.6.70-xilinx; `/dev/mmcblk0p2 on / type ext4 (ro,relatime)`; `ids` and `nftables` active; `systemd-analyze`: 2.009 s (kernel) + 27.290 s (userspace) = 29.300 s;
  `pack OK: /opt/ids/pool-factory version 1 with 6 models`; `idsd up: backend=arm input=mqtt rotate=poisson/30.0s pool=6`.
- No Mosquitto was started by this job and no replay was run; the host's own Mosquitto (started earlier by Sharwan) was still listening, so the `ids` service may have connected to it, with no traffic.
- No QEMU process was left running (`pgrep` count 0 after each boot).

## Sources downloaded
200 "Downloading" lines in the log. Three archives fell back to the Buildroot mirror `sources.buildroot.net` after the primary site failed
(`zlib-1.3.2.tar.xz`: HTTP 404 at `www.zlib.net`; `dosfstools-4.2.tar.gz` and `u-boot-2021.07.tar.bz2`: `Failed to connect: Handshake error`); all others came from the upstream sites
(github.com, ftpmirror.gnu.org, files.pythonhosted.org, cdn.kernel.org, …). The kernel and U-Boot tarballs came from the Xilinx GitHub tags named in the defconfig.
So the download URLs **were** exercised, including the fallback; a site that is down on another day can still make a rebuild fail or fall back to the mirror.

## Limitations
- QEMU only: boot time and the `ids` start are measured in QEMU (emulated ARM), not on the board; QEMU boot time varies (29.3 s here, 29.5 s and 56.8 s earlier).
- The build host is the same laptop, same Fedora toolchain, with the same installed host packages; a different distribution was not tried.
- One build only: whether two clean builds on this laptop produce identical hashes (bit-for-bit reproducibility) was not tested; only new-vs-earlier was compared.
- Evidence in `results/clean_build_finish.txt` is the script's output transcribed unchanged except one annotation of a false "build still running" line (the `pgrep` pattern matched a helper).
- The signing step was not part of this build: the factory pack in `models/pool` was already signed and `keys/pool_pub.pem` verified it (`OK: version 1, 6 models`, printed by `build.sh` before building).
- A real PYNQ-Z2, the persistent `/data` partition and the real device tree are still outside this evidence.

## Clean-up
Only the two directories created for this job (`~/br-clean`, `~/clean-clone`) were deleted after this file was committed; `~/br-clean-build.log` and `~/br-clean-finish.txt` were kept; `~/br-ids`, `~/buildroot`, `~/Downloads`, `~/Documents` and `keys_release/` were not touched.
Free space on `/` after the deletion: see the last line of this file.

Free space on `/` after deleting `~/br-clean` and `~/clean-clone`: 30,149 MiB available (`df -h ~`: 78G size, 44G used, 30G avail, 60%); 14,851 MiB were freed (15,297 MiB available just before).
