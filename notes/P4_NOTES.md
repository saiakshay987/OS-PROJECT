# P4 notes (Buildroot, security, benchmarks, report)

Every command that worked, every error and its fix, with dates. Every number with the commit and command that produced it.

## Stock PYNQ-Z2 v3.1.1, measured offline (18 Nov 2026, 21:43 IST)
Method: bench/stock_offline.sh (read-only loop mount). Output: results/stock_offline.txt.
Image 8,337,309,696 B | rootfs used 5,440 MiB | 1,628 packages | 20 units in multi-user.target.wants
| 14 setuid files | kernel: image.ub (FIT bundle) 7,147,780 B + BOOT.BIN 1,165,852 B.
RAM idle / boot time: needs the board.

## Hardened Buildroot appliance in QEMU (19 Nov 2026, IST)
Buildroot 2025.02.19, BR2_EXTERNAL tree os/buildroot/external, defconfig ids_zynq_defconfig, build dir ~/br-ids (make O=~/br-ids). Booted with qemu-system-arm xilinx-zynq-a9 (~/boot_ids.sh, patched QEMU-only DTB).
Measured on the 18:33 IST build, repo commit 01bc8ed:
- Used rootfs: 114 MiB (du -sm ~/br-ids/target) vs stock 5,440 MiB = about 2% of stock.
- sdcard.img 201,327,104 B (192 MiB; 160M rootfs partition + boot), uImage 4,659,952 B.
- setuid files: 2 (/usr/bin/busybox, dbus-daemon-launch-helper) vs 14 in stock (find / -xdev -perm -4000 -type f).
- Listening TCP (netstat -tln): 22 (dropbear) and loopback 127.0.0.53/.54:53 only.
- Root mounted ro (mount | grep ' / '), touch /x fails "Read-only file system". tmpfs on /var (32M) and /data (64M).
- systemctl --failed: only ids.service, which fails closed because no signed model pack is installed yet (expected).
Not yet measured: package count, boot time, RAM idle (RAM/boot need the board).

## Problems found and fixed
- QEMU "Could not attach PHY (-19)": QEMU's PHY is at address 7, the ZedBoard DTS says 0. Fixed with a QEMU-only DTB (zynq-zed-qemu.dtb). The real-board DTB is untouched.
- users.txt: the Buildroot users table needs 9 fields; the guide's line had 8.
- eth0 is renamed end0, so the DHCP .network file never matched. Fixed to match "eth0 end0".
- Firewall flaw: ids.service ran "nft -f" with "flush ruleset" at every start. The blocked set was emptied on every detector restart, and no firewall existed until ids started. Fixed with a separate nftables.service (loads once, before the network); ids.service requires it and its own ExecStartPre is cleared by a drop-in.
- Root stayed rw even with "ro" on the kernel line: fstab said "/dev/root / auto rw" (skeleton package, already built, not rebuilt on a config change). Fixed in post-build.sh (sed on fstab), and extlinux.conf set to ro.
- ids.service crash loop with no pack: restart counter reached 51, about 8.4 s CPU per attempt. Fixed with StartLimitIntervalSec=300, StartLimitBurst=3, RestartSec=30; it now stays failed.
- LLMNR listened on 0.0.0.0:5355 (systemd-resolved). Disabled (LLMNR=no, MulticastDNS=no).
- Host: openssl CLI missing for modelpack.py keygen (dnf install openssl). Host disk was full during the build (78 GB root), freed about 16 GB.

## Known limitations
- No RTC: journald prints "Time jumped backwards" at boot (cosmetic). Real board needs RTC or NTP.
- Kernel has no UTS namespaces, so ProtectHostname=yes in the ids hardening drop-in is ignored.
- /var is tmpfs: dropbear host keys regenerate on every boot.
- /data is tmpfs: an installed model pack does not survive a reboot. The board needs a persistent data partition.
- Output firewall policy is drop and allows no udp 67, so DHCP lease renewal (lease about 24 h) would be blocked on a long run.

## Release key (19 Nov 2026, 18:45 IST)
Key pair made with python3 common/modelpack.py keygen keys_release. Public key committed as keys/pool_pub.pem (commit 2aa68aa). Private key stays out of git (keys_release/ is in .gitignore line 9, checked with git check-ignore); backup to USB pending.

## Still open
- models/pool from P3 (not in repo): needed for the signed v2 pack, E5 T1-T6 on the real pack, and the final image that lets ids start.
- E5 mechanics were rehearsed only on a throwaway fake pack in /tmp. No numbers from that run are reported.
- E4 fingerprinting: data/unsw missing.

## Appliance vs stock, measured (20 Nov 2026, IST). QEMU values are NOT board values.
| Metric | Stock PYNQ-Z2 v3.1.1 | Our Buildroot image | Source |
|---|---|---|---|
| Used rootfs | 5,440 MiB | 114 MiB (2.1% of stock) | du -sm ~/br-ids/target |
| Packages | 1,628 | 27 (distinct Buildroot packages with files in the target; different counting method) | cut -d, -f1 packages-file-list.txt, sort -u |
| setuid files | 14 | 2 (busybox, dbus-daemon-launch-helper) | find / -xdev -perm -4000 |
| Kernel | image.ub 7,147,780 B + BOOT.BIN 1,165,852 B | uImage 4,659,952 B (6.6.70-xilinx) | ls -l |
| RAM idle | needs the board | 31 MiB used, 454 MiB available of 496 MiB (QEMU, 512 MB) | free -m, ids running |
| Boot | needs the board | multi-user target at 29.5 s, ids started at 28.2 s (QEMU, emulated CPU) | journalctl -o short-monotonic |
| Open TCP ports | not measured | 22 (dropbear) + loopback DNS stubs | netstat -tln |

## E5 update-path tests on the real signed pack (commit 190cbc8, results/e5_update_tests.txt)
Run on a laptop with common/modelpack.py and app/appliance/idsd.py, release key from keys_release/ (private key not in git). NOT run on the appliance. The appliance itself accepted the factory pack: "pack OK: /opt/ids/pool-factory version 1 with 6 models" (about 12 s after start in QEMU).
| Test | Result |
|---|---|
| T0 factory pack, release public key | OK: version 1, 6 models |
| T1 valid newer pack (v2) | installed |
| T2 one model replaced by another valid model | REJECTED: m2.npz hash mismatch |
| T3 manifest rewritten, not re-signed | REJECTED: signature check failed |
| T4 signed with another key | REJECTED: signature check failed |
| T5 old pack (v1) replayed after v2 | REJECTED: version 1 is not newer than installed 2 |
| T6 installed file corrupted | idsd rejected v2 (m0.npz hash mismatch) and rolled back to the factory pack |
Verification of the 6-model pack takes 0.19 s on the laptop (not measured on the appliance).

## Licences
report/licences-manifest.csv from make legal-info (27 target packages). Kernel, U-Boot, busybox, util-linux, nftables: GPL-2.0(+). glibc, systemd, kmod, libxcrypt: LGPL. python3: Python-2.0. python-numpy: BSD-3-Clause. python-paho-mqtt: EPL-2.0 or BSD-3-Clause. openssl: Apache-2.0. dropbear, expat, libffi: MIT. No proprietary software is in the image.

## Branches
p4/signed-pack-v1 (signed pool + E5 results; PR to p3/model-pack-v1) and p4/report-evidence (licence list + these notes). Earlier work went straight to main (d8de386, 01bc8ed, 2aa68aa, 3b4d39c).

## Hardening evidence on the Buildroot image (20 Nov 2026, QEMU)
| Measure | Before | After | Evidence |
|---|---|---|---|
| Root filesystem | rw (first boot) | ro; touch /etc/x: Read-only file system | mount, touch |
| Firewall | none until ids started; flush ruleset wiped the blocked set on each restart | nftables.service loads default-deny (input, forward, output) before the network | nft list ruleset |
| Service user, capabilities | n/a | ids user; CapInh/Prm/Eff/Bnd/Amb = 0x1000 (CAP_NET_ADMIN only) | ps, grep Cap /proc/PID/status |
| systemd exposure score | 6.1 MEDIUM (ids.service alone, no drop-in) | 4.1 OK (with hardening.conf) | systemd-analyze security --offline=true; before measured on a copy named idsplain.service, because the tool applies ids.service.d drop-ins by unit name |
| SSH | dropbear -F -R (passwords and root allowed) | dropbear -F -R -s -w (keys only, no root); no key in the image, so console only | ps |
| Kernel settings | randomize_va_space 1 | 2 (added to security/90-hardening.sysctl.conf); kptr_restrict 2, dmesg_restrict 1 | cat /proc/sys/kernel/randomize_va_space, sysctl |
| LLMNR | listening on 0.0.0.0:5355 | off (resolved.conf.d) | netstat -tln |
| Crash loop without a pack | restart counter 51, 8.4 s CPU per attempt | StartLimitBurst=3 in 300 s, RestartSec=30; unit stays failed | journalctl -u ids |
| Listening sockets | n/a | TCP 22; loopback 127.0.0.53 and .54 port 53; UDP 68 (DHCP client) | netstat -tln, -uln |
Residual risks: the serial console is a root login without a password in this QEMU build; no secure boot; MQTT without TLS (allow_anonymous true in the demo broker); the canary test does not catch a subtle backdoor, only the signature does; the signing key lives on one laptop; /data is tmpfs so installed packs do not survive a reboot; ProtectHostname has no effect because the kernel lacks UTS namespaces (kernel/ids.cfg now has CONFIG_UTS_NS, not rebuilt or verified on this image).

## Buildroot image in QEMU (measured on this laptop, NOT hardware)
Files: results/image_buildroot_qemu.csv (sh /opt/ids/bench/measure_image.sh buildroot), results/speed_buildroot_qemu.csv (python3 /opt/ids/bench/speed.py buildroot-qemu /opt/ids/pool-factory). Both transcribed from the serial console.
- Root filesystem used 96 MB (df in the guest); 114 MiB with du on the host target folder; stock 5,440 MiB. 31 MB RAM used, 55 processes, 0 kernel modules, 2 setuid files, 7 listening sockets (4 TCP, 3 UDP).
- Boot: 2.355 s kernel + 27.161 s userspace = 29.516 s (systemd-analyze). Most of it is the emulated CPU: root device wait 19.5 s, udev-trigger 12.7 s, systemd-resolved 11.8 s; network wait is not on the critical path. Not comparable with P2's PetaLinux QEMU run (different QEMU setup, 18 units masked).
- Model speed: batch 1 about 1.8 to 2.5 ms per record (408 to 561 records/s); batch 64 and 1024 about 59 to 189 us per record (5.3k to 17k records/s). Emulated ARM, not hardware speed.

## E4: can the attacker tell which model is active? (20 Nov 2026)
Data: P3's UNSW-NB15 CSVs through ml/prepare.py (257,673 records, splits 154,603 / 51,535 / 51,535, same as P3). models/scaler.json restored from git before the final run (the first run, with the scaler regenerated by prepare.py, gave identical numbers).
Commands: python ml/e4_fingerprint.py --n 3000 --budget 200 and --budget 1000. Files: results/e4_fingerprint_budget200.csv, results/e4_fingerprint_budget1000.csv.
- 508 of 6,000 candidate probes (8.5%) split the pool. 3 probes identify any of the 6 members; no pair is indistinguishable. After setup, an attack costs 4 queries (3 probes + 1).
- Attacker setup cost: the label-only random search found no evasion for most records within the budget, so the median hit the cap (201 with budget 200, 1,001 with budget 1000; totals 1,206 and 6,006). Report it as more than 1,000 queries per member (a lower bound), not as a measured price.

## Live chain on the Buildroot image (20 Nov 2026, QEMU)
results/live_chain_buildroot_qemu.txt. replay.py with --n 3000 --rate 200: 1,912 attacks, 1,697 alerts, TP 1,656, FP 41, FN 256, TN 1,047, recall 0.866, FPR 0.038; sent to alert median 16.6 ms, p95 118.3 ms. 37 swaps, 38 blocks: 8 attacker addresses and 30 benign addresses (blocked because of false positives, 60 s each). A 3,000-record sample, not the full test split. Stage-2 verdict not run (counter 0, stage2_server.py not running).

## Still open
Board numbers (RAM, boot, real swap); stage-2 verdict step; UTS_NS kernel rebuild; report assembly, slides, video; merge everything and tag v1.0.
