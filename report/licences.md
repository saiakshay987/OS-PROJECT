# Licence list (deliverable 4, constraint b)

P4, 21 Nov 2026. Sources: `report/licences-manifest.csv` (Buildroot `make legal-info`, 27 licence rows),
`report/package_manifest_buildroot.csv` (Buildroot `make show-info`, regenerated 21 Nov, 29 non-virtual target packages),
`~/br-ids/legal-info/` (licence texts and source archives, 612 MB, **not committed**: regenerate with
`os/buildroot/build.sh manifest`), and the checks listed in each section.

**Constraint b:** proprietary components are allowed only if listed and justified; everything else must be open source.

## 1. Open-source components in the Buildroot image (verified)

How checked: `show-info` reports `redistributable: True` for all 29 non-virtual target packages; the 27 rows of
`report/licences-manifest.csv` have identical versions to the 21 Nov `show-info` (script comparison, no differences); the two extra
rows in `package_manifest_buildroot.csv` (`skeleton-init-common`, `skeleton-init-systemd`, both GPL-2.0-or-later) are the root
filesystem skeletons. `find ~/br-ids/target` finds no `*.bit*`, no `*nvidia*`, no `*cuda*`, no `*torch*`, and no firmware directory.
Our own files in the image are listed in section 3.

| Package | Version | Licence (from Buildroot) | In rootfs |
|---|---|---|---|
| linux (Xilinx linux-xlnx) | 6.6.70 (`xlnx_rebase_v6.6_LTS_merge_6.6.70`) | GPL-2.0 | boot partition (and 11 `.ko` files, 0 loaded) |
| linux-headers | same | GPL-2.0 | no (build only) |
| uboot (Xilinx u-boot-xlnx, also builds `boot.bin` SPL) | `xlnx_rebase_v2024.01_2024.2` | GPL-2.0+ | boot partition |
| busybox | 1.37.0 | GPL-2.0, bzip2-1.0.6 | yes |
| systemd | 256.17 | LGPL-2.1+, GPL-2.0+ (udev), plus public-domain/BSD/MIT/CC0/OFL-1.1 files (see `licences-manifest.csv`) | yes |
| util-linux | 2.40.4 | GPL-2.0+, BSD-4-Clause, LGPL-2.1+ (libs), BSD-3-Clause, BSD-2-Clause, ISC, MIT | yes |
| util-linux-libs | 2.40.4 | LGPL-2.1+, BSD-3-Clause | no files of its own |
| kmod | 33 | LGPL-2.1+ (library), GPL-2.0+ (tools) | yes |
| kbd | 2.6.4 | GPL-2.0+ | yes |
| libcap | 2.73 | GPL-2.0 or BSD-3-Clause | yes |
| nftables | 1.1.0 | GPL-2.0 | yes |
| nftables-python | 1.1.0 | GPL-2.0 | yes |
| libnftnl | 1.2.7 | GPL-2.0+ | yes |
| libmnl | 1.0.5 | LGPL-2.1+ | yes |
| dbus | 1.14.10 | AFL-2.1 or GPL-2.0+ (library, tools), GPL-2.0+ (tools) | yes |
| expat | 2.9.0 | MIT | yes |
| dropbear | 2026.93 | MIT, BSD-2-Clause, Public domain, Unlicense, WTFPL | yes |
| glibc | 2.41 (git snapshot) | GPL-2.0+ (programs), LGPL-2.1+, BSD-3-Clause, MIT (library) | yes |
| gcc-final (runtime libraries) | 13.4.0 | GPL-3.0 with GCC runtime exception | yes |
| libxcrypt | 4.4.38 | LGPL-2.1+ | yes |
| libopenssl (openssl CLI + library) | 3.5.9 | Apache-2.0 | yes |
| libzlib | 1.3.2 | Zlib | yes |
| libffi | 3.4.6 | MIT | yes |
| python3 | 3.12.15 | Python-2.0, others | yes |
| python-numpy | 1.25.0 | BSD-3-Clause, MIT, Zlib | yes |
| python-paho-mqtt | 2.1.0 | EPL-2.0 or BSD-3-Clause | yes |
| tzdata | 2026e | Public domain | yes |
| skeleton-init-common, skeleton-init-systemd | n/a | GPL-2.0-or-later (LGPL-2.1-or-later for `factory/var.mount`) | yes |

Counting: `packages-file-list.txt` lists 27 names with files in the root filesystem (one is Buildroot's `toolchain`
pseudo-package), so 26 real packages; legal-info has 27 rows because it includes `linux-headers`, `uboot` and `util-linux-libs` (no
files in the rootfs) and omits the two skeletons. The "27" of the earlier notes therefore counts two different sets.

Copyleft note: the kernel, BusyBox, U-Boot, util-linux, nftables and glibc programs are GPL; the corresponding source archives are
in `~/br-ids/legal-info/sources/` and the build is reproducible from `os/buildroot/` (our kernel changes are only the two config
fragments, no patches). No proprietary software is in the Buildroot image.

## 2. Proprietary / non-open components (listed and justified)

| Component | Where it is used | In the Buildroot image? | In the PetaLinux image? | Justification |
|---|---|---|---|---|
| **AMD/Xilinx Vivado 2024.1** (build 5076996) and **Vitis HLS 2024.1** | P1's laptop (`/tools/Xilinx`, `notes/P1_NOTES.md`): turn the six models into FPGA IP and `hw/bit/m0.bit.bin`; reports in `hw/reports/` (header of `m0_impl_util.rpt`: Vivado v2024.1) | **No**: no `.bit` file and no Xilinx tool in `~/br-ids/target`; `post-build.sh` does not copy `hw/` | **Not shown to be.** `os/petalinux/` contains no bitstream. TODO(P2): confirm | The only supported flow from a quantised model to a Zynq-7020 bitstream; no open-source toolchain was in scope. Build tool only. The generated `hw/bit/m0.bit.bin` (4,045,568 B) is committed in the repo and contains AMD/Xilinx-licensed IP (the Zynq PS7 block) in generated form. TODO(P1): state the Vivado edition/licence used and whether the generated bitstream may be redistributed in this repo. |
| **AMD/Xilinx PetaLinux 2024.1** and the ZC702 BSP | P2's laptop (`notes/P2_NOTES.md` section 1): builds the PetaLinux image | No | The image is built by it. Its contents are Yocto-built open-source packages (229 in `rootfs.manifest`), **but the licence manifest of the image was not checked**: it is not in the repo. TODO(P2): attach `license.manifest` from `build/tmp/deploy/licenses/` and list anything not open source (for example anything taken from the BSD) | Required for the PetaLinux path and for Xilinx kernel/U-Boot trees; the Buildroot path (open tools only) is the answer to the open-source constraint. Build tool only. |
| **NVIDIA GPU driver, CUDA runtime** (pulled in by the CUDA build of PyTorch) | P3's RTX 4050 laptop: `ml/train_stage2.py`, `ml/qat.py`, `app/laptop/stage2_server.py` (`requirements.txt` says "CUDA build on the RTX 4050 laptops") | **No** (`grep -rl torch` over the repo finds only `ml/qat.py`, `ml/train_stage2.py`, `app/laptop/stage2_server.py`; none is installed in the image; no torch in `~/br-ids/target`) | **No** (same grep: no torch in `os/petalinux/`) | Stage 2 (naming the attack type) and model training run on the laptop. The GPU is a speed choice, not a functional need: `stage2_server.py` picks `cuda` if available and otherwise `cpu` (line 6), so the system works without any proprietary component, only slower. PyTorch itself is BSD-style open source; only the NVIDIA driver and CUDA libraries are proprietary. |
| PYNQ-Z2 stock image v3.1.1 (Ubuntu-based, 1,628 packages) | Baseline only (`bench/stock_offline.sh`, read-only mount) | No | No | Measured, never booted or redistributed. Mixed open-source licences; not part of any deliverable image. |
| UNSW-NB15 dataset | `ml/prepare.py` input; `data/` is git-ignored | No | No | Data, not software; not committed. Its use terms come from UNSW (academic research with citation, per the dataset page). TODO(P3): quote the exact terms and citation in the report. |
| Our own signed model pack (`models/pool/`, `keys/pool_pub.pem`) | Baked into both images | Yes | Yes | Our own work, not third-party. The private key `keys_release/` is never committed. |

## 3. Our own code
Written by the four team members and installed in the image: `app/appliance/idsd.py`, `fpga_regs.py`, `common/qmlp.py`, `common/modelpack.py`,
`security/*` configs, `bench/*`, `os/*`. **The repository has no `LICENSE` file**, and the only licence declaration is
`LICENSE = "MIT"` in `os/petalinux/.../ids-app.bb`. TODO(team): pick one licence (MIT would match the recipe) and add `LICENSE`.

## 4. Laptop-side tools (not in any image)
| Tool | Version here | Licence | How checked |
|---|---|---|---|
| Eclipse Mosquitto | 2.1.2 | EPL-2.0 | `rpm -q --qf '%{LICENSE}' mosquitto` |
| QEMU (`qemu-system-arm`) | 10.2.2 | mixed, includes GPL-2.0 and BSD (see rpm) | `rpm -q --qf '%{LICENSE}' qemu-system-arm-core` |
| numpy / pandas / paho-mqtt / pytest (laptop venv) | 2.4.6 / 3.1.1 / 2.2.0 / 9.2.0 | BSD-3-Clause (+0BSD, MIT, Zlib, CC0 for numpy) / BSD-3-Clause / EPL-2.0 OR BSD-3-Clause / MIT | `importlib.metadata` in `.venv` |
| matplotlib | 3.11.2 | Matplotlib licence (PSF-style) | `importlib.metadata` in `.venv` |
