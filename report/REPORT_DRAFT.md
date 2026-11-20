# A minimal, hardened Linux appliance for a rotating-model intrusion detector — final report (DRAFT)

OS course project, Track E. Draft assembled by P4 on 21 Nov 2026 from `notes/P1_NOTES.md` … `P4_NOTES.md`, `results/`, `cosim/` and the
files named in each table. **Every number carries its source file. QEMU rows are labelled "measured in QEMU (emulated ARM), not on the
board".** Where a teammate's input is missing there is a visible `TODO(owner)` line. Companion files: `report/deliverables_audit.md`,
`report/size_comparison.md`, `report/licences.md`, `report/demo_runbook.md`.

## Limitations and what is imitated (read this first)

1. **There is no PYNQ board.** No FPGA path, no real-board RAM, boot or swap numbers; `hw/overlay/`, `app/appliance/fpga_regs.py` and the
   real bitstream flow are untested on hardware. The models run as integer code on the ARM CPU in QEMU, and every swap *imitates* the
   FPGA load (`SWAP_MS` 207 ms, the Xilinx FPGA-manager figure; `notes/P1_NOTES.md`). A 4,045,568 B bitstream for m0 exists (`hw/bit/m0.bit.bin`).
2. **All timing is emulated.** QEMU boot of the *same* Buildroot image took 29.5 s (`results/image_buildroot_qemu.csv`) and 56.8 s
   (`results/live_chain_buildroot_qemu_50.txt`), so QEMU boot time is not a reliable measure.
3. **First-alert blocking also blocks most benign hosts.** A source is blocked on its first alert; with a 4-5% per-record false-positive
   rate most benign hosts are blocked (30 of 50 benign sources in `results/live_chain_buildroot_qemu.txt`; 34/50 in P2's run, `notes/P2_NOTES.md` §5).
   A design limitation, not a bug; future work: block after k alerts in a window.
4. **Serial console root login has no password** in the QEMU build; **no secure boot**; **MQTT without TLS or authentication** (`allow_anonymous true`,
   `app/laptop/mosquitto.conf`; the fix is sketched in `security/mqtt-auth.md`).
5. **The signing key lives on one laptop** (`keys_release/`, git-ignored); the USB backup is still pending (`notes/P4_NOTES.md`).
6. **`/data` is tmpfs** in the Buildroot image, so an installed model pack does not survive a reboot; a board needs a persistent data partition.
7. **Kernel before/after is missing.** No kernel without the `ids.cfg` fragment was built, so no size or boot-time effect of the fragment can be claimed
   (section 3). `CONFIG_UTS_NS` *is* in the final Buildroot kernel (section 3) — the earlier statement "never rebuilt or verified" is out of date.
8. **No PYNQ-Z2 device tree.** The Buildroot image uses the ZedBoard DTS (closest emulated board); the PetaLinux image uses the ZC702 BSP.
9. **Stage-2 accuracy has not been compared with true labels**; the stage-2 step is shown to run (verdict names), nothing more. Stage 2 has not been
   run with the Buildroot image in a measured run.
10. **Record loss at high rates.** On the Buildroot guest, runs with stage 2 at 200 records/s processed only about 1,340-1,580 of 3,000 records, so their
    recall (0.38-0.43) is *not* a detector result and is not reported (figures from the 21 Nov run log; TODO(P4): save the status counters as a file).
    The Buildroot 200/s run without stage 2 and the clean 50/s run processed all 3,000 records.
11. **Unexplained difference with PetaLinux.** P2's PetaLinux guest ran 300 records/s with stage 2 and kept recall 0.871 (`notes/P2_NOTES.md`, "Live chain with P3"),
    while the Buildroot guest lost records at 200/s. Known setup differences: Buildroot guest = upstream QEMU 10.2.2 `xilinx-zynq-a9`, `-m 512`, 1 vCPU (`nproc` = 1),
    root on an SD ext4 image, `os/buildroot/qemu/boot_ids.sh` (no `-smp`/`-cpu`); PetaLinux guest = `petalinux-boot --qemu` (Xilinx QEMU), about 1 GiB RAM (MemTotal 1,029,224 kB),
    root in an initramfs, replay and stage 2 on other laptops over a LAN (`notes/P2_NOTES.md`). P2's QEMU options (`-smp`) are not recorded. **No cause is confirmed.**
12. **Not measured on the board:** stock-image RAM and boot time; every Buildroot/PetaLinux RAM and boot figure below is QEMU.

## Task 1 — Requirements and why a stock distribution does not fit

**Requirements** (README contract, `README.md`): a single-purpose appliance that receives 61-byte flow records over MQTT or UDP, classifies them with one of six
2-4-bit integer MLPs (rotated at random times), adds attacking sources to a firewall set, accepts only signed and canary-tested model packs, runs from a read-only root, and
has a small attack surface and image.

**Stock baseline.** PYNQ-Z2 v3.1.1 (Ubuntu-based), measured offline by `bench/stock_offline.sh` (read-only loop mount; `results/stock_offline.txt`, re-checked 21 Nov, `report/size_comparison.md`):

| Metric | Stock PYNQ-Z2 v3.1.1 | Source |
|---|---|---|
| SD image | 8,337,309,696 B | `results/stock_offline.txt` |
| Root filesystem used (`du -sx --block-size=1M`; `df -m`) | 5,440 MiB; 5,440 MiB | `results/stock_offline.txt`; `df -m` on the mount, 21 Nov |
| Packages (dpkg) | 1,628 | `results/stock_offline.txt` |
| Units in `multi-user.target.wants` | 20 | `results/stock_offline.txt` |
| setuid files | 14 | `results/stock_offline.txt` |
| Kernel + boot | `image.ub` 7,147,780 B (FIT bundle) + `BOOT.BIN` 1,165,852 B | `results/stock_offline.txt` |
| RAM idle, boot time | **TODO(board)** needs the PYNQ-Z2 | — |

**Why it does not fit.** 5.4 GB and 1,628 packages for a task that needs a Python interpreter, numpy, an MQTT client and a firewall; 14 setuid programs and 20 boot units are attack surface the
appliance never uses; a general-purpose login-oriented userland cannot be shown to be minimal or reproducible. (The PetaLinux and Buildroot images the project built are measured below.)

## Task 2 — Build systems: Buildroot vs PetaLinux

| Aspect | Buildroot (P4) | PetaLinux 2024.1 (P2) | Source |
|---|---|---|---|
| Version / host | Buildroot 2025.02.19, Fedora laptop | PetaLinux 2024.1, ZC702 BSP, Ubuntu 22.04.5 | `os/buildroot/kernel/README.md`; `notes/P2_NOTES.md` §1 |
| Kernel | Xilinx linux-xlnx 6.6.70, `xilinx_zynq_defconfig` + 2 fragments | 6.6.10-xilinx-v2024.1 | `os/buildroot/kernel/README.md`; `notes/P2_NOTES.md` |
| Init | systemd 256.17 | systemd (set in `petalinux-config -c rootfs`) | `report/licences.md`; `notes/P2_NOTES.md` |
| Packages in the image | 26 (with files in rootfs), 29 non-virtual target packages incl. kernel/U-Boot/headers | 229 (Yocto `rootfs.manifest`) — **not comparable** | `report/package_manifest_buildroot.csv`; `notes/P2_NOTES.md` |
| Build time | not timed (the log timestamps do not give a clean figure) | first full build 37m13s; later 3m14s, 4m40s, 1m26s | `notes/P2_NOTES.md` §4 |
| Build tree size | `~/br-ids` 14 GB (`du -sh`, 21 Nov, includes host tools and the toolchain) | `build/` 17 GB (`du -sh`, 20 Nov) | `du -sh`; `notes/P2_NOTES.md` §4 |
| Configuration kept in git | `ids_zynq_defconfig` + `board/ids/` (BR2_EXTERNAL); kernel `.config` copied in `os/buildroot/kernel/` | `project-spec/meta-user/` only (recipes, `petalinuxbsp.conf`, `user-rootfsconfig`) | `os/buildroot/`, `os/petalinux/` |
| Reproducibility from the repo | `os/buildroot/build.sh configure` in a fresh clone gives the same `.config` as the real build (2 s, 21 Nov, apart from paths and version string); the long build was **not** repeated from a clean clone | manual steps: BSP download, `petalinux-create`, password hash, `petalinux-config -c rootfs`; the kernel `bbappend` is **not in the repo** | `report/deliverables_audit.md`; `os/petalinux/README.md` |
| Licence tooling | `make legal-info` and `show-info` | Yocto `license.manifest` (**TODO(P2)** not in repo) | `report/licences.md` |
| Tool licences | open | proprietary Xilinx tool, listed in `report/licences.md` | `report/licences.md` |

**Reading.** Buildroot gave the smaller and fully scripted image (97.9% smaller than stock by `du`; `report/size_comparison.md`) and an open toolchain; PetaLinux is the path that fits the Xilinx board
support (FPGA manager, device-tree flow) and was used for the co-simulation demo (`cosim/DEMO.md`). The 26 vs 229 package counts come from different tools and are not a like-for-like measure.

## Task 3 — Kernel configuration, drivers, size and boot time

Final Buildroot kernel `.config`: `os/buildroot/kernel/linux-6.6.70-xilinx.config` (provenance in `os/buildroot/kernel/README.md`). Fragments: `kernel/ids.cfg` (P1) then `os/buildroot/external/board/ids/linux-extra.cfg` (P4).

| Option group | Result in the final Buildroot `.config` | Source |
|---|---|---|
| nftables (`NF_TABLES`, `_INET`, `_IPV4`, `NFT_CT`, `_LIMIT`, `_REJECT`), conntrack | `=y` | `.config` grep |
| `NFT_COUNTER` | no such symbol in the 6.6.70 tree: the fragment line has no effect | `grep NFT_COUNTER net/netfilter/Kconfig` (no match) |
| `OVERLAY_FS`, `STRICT_DEVMEM` | `=y` | `.config` |
| FPGA manager/bridge/region, `OF_OVERLAY`, `OF_CONFIGFS`, `UIO`, `UIO_PDRV_GENIRQ` | `=y` (board path, untested) | `.config` |
| `NAMESPACES`, `UTS_NS` | `=y`; the guest has `/proc/self/ns/uts` | `.config`; `results/live_chain_buildroot_qemu_50.txt` |
| `SOUND`, `DRM`, `FB`, `MEDIA_SUPPORT`, `WLAN`, `BT`, joystick, touchscreen | not set | `.config` |
| Modules | `MODULES=y`, 11 `.ko` files shipped, 0 loaded | `find target -name '*.ko'`; `results/image_buildroot_qemu.csv` |

| Kernel | Buildroot | PetaLinux | Source |
|---|---|---|---|
| Version | 6.6.70-xilinx | 6.6.10-xilinx-v2024.1 | `.config` header; `notes/P1_NOTES.md` |
| Kernel image | `uImage` 4,677,360 B; `vmlinux` 13,425,428 B (20 Nov 21:55 build) | `zImage` 4,560,016 B; `vmlinux` 13,468,952 B | `ls -l`; `notes/P1_NOTES.md`, `notes/P2_NOTES.md` |
| Boot, measured in QEMU (emulated ARM), not on the board | 29.516 s (2.355 kernel + 27.161 user) and 56.826 s (4.068 + 52.758), same image, two boots | 13.4 s before service pruning, 9.6 s after (*pruning of services, not of the kernel*) | `results/image_buildroot_qemu.csv`; `results/live_chain_buildroot_qemu_50.txt`; `notes/P2_NOTES.md` |

**Before/after.** TODO(P1): the kernel size and boot time **before** and after the `ids.cfg` fragment. No "before" kernel exists for either image; P2 gave none and P4 built none
(`notes/P1_NOTES.md`). The PetaLinux `.config` is on P2's laptop and **not committed** (TODO(P2)). A kernel-only rebuild with the base `xilinx_zynq` defconfig would give the Buildroot "before" (not run; a kernel compile).
The two boot times are not comparable (different QEMU, RAM, root type, units masked: `notes/P4_NOTES.md`).

## Task 4 — Minimal userland: what is in, what is out, and why

Buildroot image: 26 packages with files in the rootfs (`report/package_manifest_buildroot.csv`; licences in `report/licences.md`). Largest by installed file size (regular files listed in
`~/br-ids/build/packages-file-list.txt`, 70.3 MiB of the 102.6 MiB `rootfs.tar`; the remainder is not attributed to packages there):

| Package | Installed size | Why it is included |
|---|---|---|
| python-numpy 1.25.0 | 21.7 MiB | integer MLP arithmetic (`common/qmlp.py`) |
| systemd 256.17 (+ networkd, resolved, analyze) | 21.4 MiB | init, service sandboxing and `systemd-analyze security` used as hardening evidence; chosen over BusyBox init for the sandbox options |
| python3 3.12.15 | 9.1 MiB (listed files) | runs `idsd.py` |
| libopenssl 3.5.9 (+ openssl CLI) | 5.3 MiB | model-pack signature check (`common/modelpack.py`; `openssl-bin` in P2's list) |
| gcc-final (runtime libs only) | 2.1 MiB | libgcc/libstdc++ runtime for Python/numpy; no compiler on the target (`ls target/usr/bin` has no gcc/cc/make) |
| kbd 2.6.4 | 2.1 MiB | selected by systemd's `vconsole` tool (`select BR2_PACKAGE_KBD` in `package/systemd/Config.in`, default y); not needed by the detector, candidate for removal (not done) |
| glibc, tzdata, util-linux, busybox, nftables, dbus, dropbear, kmod, libcap, expat, libffi, libzlib, libxcrypt, libmnl, libnftnl | 0.4-1.9 MiB each | C library and base tools; nftables = firewall with a `blocked` set; dbus is a runtime dependency selected by systemd (`package/systemd/Config.in`); dropbear for optional key-only SSH (no key installed, so console only); kmod for module loading |
| python-paho-mqtt 2.1.0 | small | MQTT client for flows, alerts, status, verdicts |
| nftables-python 1.1.0 | not itemised | **Not needed:** `idsd.py` calls the `nft` command through `subprocess` and never imports the Python bindings; the option `BR2_PACKAGE_NFTABLES_PYTHON=y` is in the build `.config` (not an explicit line of `ids_zynq_defconfig`, so it came in by default). Candidate for removal; the saving was not measured. |

**Excluded** (and why): graphical stack, sound, DRM, media, WLAN, Bluetooth (kernel options off, `os/buildroot/kernel/README.md`); package manager (no dpkg/opkg: `packages` = NA in
`results/image_buildroot_qemu.csv`); compiler and build tools; Jupyter and the PYNQ userland (stock has 1,628 packages); NFS, rpcbind, telnet/ftp inetd, tcf-agent, extra syslogs, userdbd (present in PetaLinux's stock
BSP, masked by P2's recipe, **absent** from Buildroot: `notes/P2_NOTES.md` baseline section); password SSH (dropbear `-s -w`).

PetaLinux image: packages added by us were `python3`, `python3-numpy`, `python3-paho-mqtt`, `nftables`, `openssl-bin`, `ids-app` on top of the BSP's 229-package rootfs; 18 units masked, services running 18 -> 9, listening sockets
23 -> 1, setuid 17 -> 9 (the setuid drop is unexplained and not credited to hardening) — all measured in QEMU (`notes/P2_NOTES.md`).

## Task 5 — Init, read-only root, hardening, signed updates

All Buildroot rows: measured in QEMU (emulated ARM), not on the board (`notes/P4_NOTES.md` hardening table, re-checked 21 Nov where noted).

| Measure | Before | After | Evidence |
|---|---|---|---|
| Root filesystem | rw on first boot | `/dev/mmcblk0p2 on / type ext4 (ro,relatime)` (re-checked 21 Nov); `touch` on `/etc` fails | `results/live_chain_buildroot_qemu_50.txt`, `results/demo_rehearsal_buildroot_qemu.txt` |
| Firewall | none until `ids` started; `flush ruleset` emptied the blocked set on each restart | `nftables.service` loads default-deny before the network; `ids` requires it | `notes/P4_NOTES.md`; `security/nftables.conf`; `post-build.sh` |
| Service user, capabilities | n/a | user `ids`, only `CAP_NET_ADMIN` (mask `0x1000`) | `notes/P4_NOTES.md` (not re-run) |
| `systemd-analyze security` exposure (`ids.service`) | 6.1 MEDIUM | 4.1 OK with the hardening drop-in | `notes/P4_NOTES.md` (measured before the UTS-namespace rebuild; not re-measured) |
| SSH | password + root | dropbear `-s -w` (keys only, no root), no key installed | `notes/P4_NOTES.md` |
| ASLR / kernel pointers | `randomize_va_space` 1 | 2; `kptr_restrict` 2, `dmesg_restrict` 1 | `notes/P4_NOTES.md`; `randomize_va_space` 2 re-read on 21 Nov in `results/live_chain_buildroot_qemu_50.txt` |
| LLMNR on 0.0.0.0:5355 | listening | off | `notes/P4_NOTES.md` |
| Crash loop with no pack | counter 51, 8.4 s CPU per attempt | `StartLimitBurst=3` in 300 s, `RestartSec=30` | `notes/P4_NOTES.md`; `post-build.sh` |
| `ProtectHostname=yes` | ignored (no UTS namespace) | kernel now has UTS namespaces, so the option can take effect; the effect itself is not measured | section 3 |
| Listening sockets (Buildroot) | – | 7 (4 TCP, 3 UDP); stock not measured | `results/image_buildroot_qemu.csv`, `notes/P4_NOTES.md` |

**Signed updates (E5)** — run on the laptop with `common/modelpack.py` and `app/appliance/idsd.py`, release key from `keys_release/` (private key not in git), **not on the appliance**
(`results/e5_update_tests.txt`): T0 factory pack verifies (version 1, 6 models); T1 newer v2 installed; T2 one model swapped, **rejected** (hash mismatch); T3 manifest rewritten, **rejected** (signature);
T4 signed with another key, **rejected**; T5 old pack replayed, **rejected** (version 1 not newer than 2); T6 corrupted install, rolled back to the factory pack. Verifying the 6-model pack takes 0.19 s on the laptop.
On the appliance only the factory pack has been accepted: "pack OK: /opt/ids/pool-factory version 1 with 6 models" (`results/demo_rehearsal_buildroot_qemu.txt`).
**Residual risks:** the limitations list above (console root login, no secure boot, MQTT without TLS, key on one laptop, tmpfs `/data`); the canary test cannot catch a subtle backdoor, only the signature does.

## Task 6 — Running the image and the end-to-end demo

Buildroot image, `os/buildroot/qemu/boot_ids.sh`, broker on the laptop at 10.0.2.2 from the guest. **Measured in QEMU (emulated ARM), not on the board.** Runbook: `report/demo_runbook.md`.

| Run | Records / rate | Processed (appliance `recs`) | Alerts, TP/FP/FN/TN | Recall / FPR | Stage 2 | Source |
|---|---|---|---|---|---|---|
| Clean run, freshly booted guest | 3,000 at 50/s | 3,000 of 3,000 (counter 0 before) | 1,710; 1,666/44/246/1,044 | 0.871 / 0.040 | not running (verdicts 0) | `results/live_chain_buildroot_qemu_50.txt` |
| 20 Nov run | 3,000 at 200/s | 3,000 of 3,000 (`recs 3000`) | 1,697; 1,656/41/256/1,047 | 0.866 / 0.038 | not running | `results/live_chain_buildroot_qemu.txt` |
| PetaLinux, P3's laptop sends, P2's guest | 5,000 at 300/s | counters cumulative, fraction not verified (recall in line with the others) | 2,830; 2,747/83/407/1,763 | 0.871 / 0.045 | running (journal shows 8,432 VERDICT lines since boot, all runs) | `notes/P2_NOTES.md`, "Live chain with P3" |

Appliance counters in the Buildroot rows are the first run after a boot; the replay summary is used for recall and FPR; the replay latency is not reported. Other Buildroot runs (stage 2 at 200/s; 50/s with cumulative counters, recall 0.769 and 0.827)
are **excluded**: records lost or processed fraction unverified (limitations 10-11). Blocks: 38 addresses after the 200/s run, 8 attackers (10.0.9.1-8) and 30 benign (`results/live_chain_buildroot_qemu.txt`); 52 blocks in the clean 50/s run (split not captured).
Swaps: 7 in the 60 s clean run, 124 records handled by the ARM fallback model during swap windows (4.1%).

**Demo rehearsal findings** (`results/demo_rehearsal_buildroot_qemu.txt`): changing `ROTATE` in `/data/ids.conf` and restarting works (rotate=off gives 0 SWAP lines; poisson/5 s gives a SWAP every 4-5 s). The live attacker script (`app/laptop/attack_demo.py`) did **not**
reproduce "evasion works every time with rotation off": it reported evasions that were then blocked 30 of 31 times, and a copy with a 0.5 s alert wait found none. Most likely a timing artifact of the 80 ms wait in the emulated guest (not proven). TODO(P3).

**Co-simulation** (P1/P2, `cosim/DEMO.md`, `cosim/NOTES.md`): Linux in QEMU talks to the Verilated RTL of m0 through a remote-port bridge; Check R 564/564, Check C 64/64 canary records match, `devmem 0x43C00000` reads idle — a functional check of one model's registers, not timing and not the board.

**FPGA numbers (estimates, not measurements on a board).** HLS estimates for the six models on xc7z020 (`notes/P1_NOTES.md`, `hw/reports/*_csynth.rpt`): latency 193-291 cycles for m0-m3 and m5, 5,412 for m4 (default) or 289 (fast variant); LUT 7,445-16,690; DSP 0; all fit. m0 post-implementation: 8,296 LUT (15.6%), no timing violation reported, bitstream 4,045,568 B (`hw/bit/m0.bit.bin`).

## Task 7 — Evaluation against the stock distribution

All Buildroot and PetaLinux values: measured in QEMU (emulated ARM), not on the board, unless the row says "host". Sizes are host measurements of files.

| Metric | Stock PYNQ-Z2 | Buildroot | PetaLinux | Source |
|---|---|---|---|---|
| Root used (`du`, 4 KiB blocks) | 5,440 MiB | **114 MiB** (97.9% smaller) | n/a (RAM root) | `report/size_comparison.md` (host) |
| Root used (`df -m`) | 5,440 MiB | 96 MiB (98.2% smaller) | – | `report/size_comparison.md` (host mount; guest `root_used_mb` 96 in `results/image_buildroot_qemu.csv`) |
| Root as uncompressed archive | 5,218,332,637 B apparent | `rootfs.tar` 107,591,680 B (97.9% smaller) | `rootfs.cpio` 130,197,504 B (97.5% smaller) | `report/size_comparison.md`; `notes/P2_NOTES.md` |
| Packages | 1,628 | 26 | 229 (Yocto) | different methods, not comparable |
| setuid files | 14 | 2 | 17 -> 9 | `results/stock_offline.txt`; `results/image_buildroot_qemu.csv`; `notes/P2_NOTES.md` |
| RAM used (QEMU) | not measured (needs board) | 31 MB (`free -m`) | 31.8 MiB (hardened) | `results/image_buildroot_qemu.csv`; `notes/P2_NOTES.md` |
| Processes | not measured | 55 (20 Nov) / 58 (21 Nov, fresh) | 61 | `results/image_buildroot_qemu.csv`; `results/live_chain_buildroot_qemu_50.txt`; `notes/P2_NOTES.md` |
| Listening sockets | not measured | 7 | 1 (UDP 68) | same |
| Boot (QEMU, emulated CPU) | not measured (needs board) | 29.5 s and 56.8 s | 13.4 s -> 9.6 s | see Task 3 |
| Kernel image | `image.ub` FIT 7,147,780 B (not like-for-like) | `uImage` 4,677,360 B | `zImage` 4,560,016 B | `report/size_comparison.md` §4 |

**Constraint c (image at least 40% smaller than stock): MET for the root filesystem** — 97.9% by `du`, 98.2% by `df`, 97.9% by archive size for Buildroot; 97.5% by archive size for PetaLinux (P2's figure, not re-measured here). The whole SD image file is 97.6% smaller
(201,327,104 B vs 8,337,309,696 B). The kernel images are not like-for-like and are not used for the claim.

**Detector results (feature space and QEMU), from P3 and P4:**

| Result | Value | Source |
|---|---|---|
| Pool accuracy / recall / FPR (integer models, 51,535-record test split) | accuracy 0.8907-0.9131, recall 0.8449-0.8912, FPR 0.0289-0.0485; float baseline accuracy 0.9320 | `models/metrics.csv`; `notes/P3_NOTES.md` |
| E2, knobs-only attacker, static member vs rotation every 1 query | evasion per session 0.018 vs 0.052; an evasion still works after a swap on 0.209 of members | `results/e2_rotation.csv` |
| E2, attacker that can also set the TTL (tier A) | static 0.480; rotation 0.508-0.638; long-run value drops only from 0.48 to about 0.37; 21-34% of evasions beat all six members | `notes/P3_NOTES.md` (E2 tier A), `results/e2_rotation_tierA.csv` — **rotation does not protect against this attacker** |
| E3 blind window (laptop daemon): `arm` fallback absorbs the swap | recall 0.872-0.875 for swap 34-550 ms | `results/e3_blind_window.csv`; `notes/P2_NOTES.md` |
| E4 fingerprinting | 3 probes identify any of the 6 members; no indistinguishable pair; 8.5% of probes split the pool; setup cost more than 1,000 queries per member (lower bound) | `results/e4_fingerprint_budget1000.csv`; `notes/P4_NOTES.md` |
| E5 signed updates | T2-T5 rejected, T6 rolled back | `results/e5_update_tests.txt` |

TODO(P3): quote the final E1/E1c figures chosen for the abstract; TODO(P1): the timing-leak analysis in `notes/P1_NOTES.md` is an estimate, not a measurement.

## Task 8 — Repository, reproducibility, limitations, licences

**Repository layout** (`README.md`): `app/`, `common/`, `ml/`, `hw/`, `kernel/`, `os/buildroot/`, `os/petalinux/`, `security/`, `bench/`, `cosim/`, `results/`, `notes/`, `report/`. CI runs `pytest -q` (`.github/workflows/ci.yml`); `pytest -q` passes (5 tests, 21 Nov).
The top-level `README.md` is stale in places (it still says real results are "not produced yet" and warns about fake data) — TODO(team).

**Reproduce the Buildroot image:** `os/buildroot/build.sh build` (`configure` = 2 s check, verified from a fresh clone; `build` = hours; `manifest` regenerates `report/package_manifest_buildroot.csv` and the licence manifest). Then `os/buildroot/qemu/boot_ids.sh`.
Inputs from the repo: `keys/pool_pub.pem`, signed `models/pool/`. Remaining manual steps: signing a *new* pack with the private key, the persistent `/data`, the PYNQ-Z2 device tree.
**Reproduce PetaLinux:** `os/petalinux/README.md` — manual steps remain (BSP, password hash, rootfs menu); the kernel `bbappend` and the PetaLinux `.config`/device tree are not in the repo (TODO(P2)).
Commit hashes: record `git rev-parse --short HEAD` of the tagged commit here: TODO(P4) at tagging time.

**Licences:** `report/licences.md` (open-source list per package from `make legal-info`; separate table of proprietary / non-open tools with justification: Xilinx Vivado/Vitis HLS and PetaLinux as build tools, NVIDIA driver/CUDA for stage 2 on the laptop).
No proprietary component is in the Buildroot image. TODO(team): add a `LICENSE` file for our own code; TODO(P2): PetaLinux `license.manifest`; TODO(P1): Vivado edition and bitstream redistribution terms.

**Open items by owner:** P1 — kernel before/after, final PetaLinux `.config`; P2 — rootfs sizes confirmation, PetaLinux manifest/licence manifest, device tree, manual-step list; P3 — stage-2 accuracy against true labels, `models/stage2.pt` availability, `attack_demo.py` wait window; P4 — clean-clone build test, board numbers, tag.
