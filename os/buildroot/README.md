# os/buildroot/ (P4) — the hardened Buildroot image

Commit only this BR2_EXTERNAL tree, the defconfig and the notes here; never `output/` (the build lives outside the repo, default `~/br-ids`).

```
os/buildroot/
├── build.sh                       build from a clean clone: configure | build | manifest | all
├── gen_manifest.py                show-info JSON + packages-file-list -> report/package_manifest_buildroot.csv
├── qemu/boot_ids.sh               boot the image in QEMU (makes the QEMU-only DTB, PHY address 7)
├── kernel/                        final kernel .config (6.6.70-xilinx) + README: versions, what the fragments did
├── dts/                           ZedBoard DTS sources, decompiled DTB, QEMU-DTB diff + README (other DT files listed there)
└── external/                      BR2_EXTERNAL tree (name IDS)
    ├── external.desc, external.mk, Config.in
    ├── configs/ids_zynq_defconfig <- 'make savedefconfig' output (differs from the build's own only by 3 default-valued lines)
    └── board/ids/
        ├── users.txt              the 'ids' service user (9 fields)
        ├── linux-extra.cfg        kernel fragment 2 (kernel/ids.cfg from P1 is fragment 1)
        └── post-build.sh          installs app, firewall, hardening, public key and factory pack from the repo; ro root; dropbear keys-only
```

## Reproduce (summary; `build.sh` does steps 1-4)
1. Buildroot **2025.02.19** tarball in `$BUILDROOT_DIR` (default `~/buildroot`; `build.sh` downloads it if absent).
2. `make -C $BUILDROOT_DIR O=$OUT BR2_EXTERNAL=<repo>/os/buildroot/external ids_zynq_defconfig`
3. `make -C $BUILDROOT_DIR O=$OUT BR2_EXTERNAL=<repo>/os/buildroot/external -j$(nproc)` (the long step)
4. `post-build.sh` runs inside step 3. Inputs it needs from the repo: `keys/pool_pub.pem`, `models/pool/` (signed pack), `app/appliance/`, `common/`, `security/`, `bench/`.
5. Outputs: `$OUT/images/sdcard.img`, `uImage`, `zynq-zed.dtb`, `rootfs.ext4`, `rootfs.tar`; boot with `qemu/boot_ids.sh`.

Manual steps that remain: signing a **new** pack (release private key on one laptop, `python3 common/modelpack.py sign ...`), the
`/data` persistence (tmpfs in this image), the PYNQ-Z2 device tree and every real-board step (no board). A full clean-clone
build has **not** been re-run from this file; see `report/deliverables_audit.md`.
