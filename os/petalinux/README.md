# os/petalinux/ (P2)

PetaLinux recipe files for the IDS appliance. Commit `project-spec/` only (build output is git-ignored).
`ids-app.bb`, `ids.service` and `fstab.example` at this level are the original starting points; the
working copies live under `project-spec/meta-user/` with the same relative paths as in a PetaLinux project:

```
project-spec/meta-user/
  conf/petalinuxbsp.conf          read-only rootfs, build-time user (hash is a placeholder)
  conf/user-rootfsconfig          adds the user packages to the rootfs menu
  recipes-apps/ids-app/ids-app.bb the recipe
  recipes-apps/ids-app/files/     everything the recipe installs
```

To use them, copy `project-spec/meta-user/` over the same path in your PetaLinux project
(here: `~/plx/ids-os`).

## Build and boot

```sh
source <petalinux-install-dir>/settings.sh
cd ~/plx/ids-os
petalinux-build
petalinux-boot --qemu --kernel
```

## What the recipe installs

| Path on target | Source |
|---|---|
| `/opt/ids/idsd.py`, `fpga_regs.py`, `qmlp.py`, `modelpack.py` | detector daemon and helpers |
| `/opt/ids/pool-factory/` | signed known-good model pack (`manifest.json`, `manifest.sig`, `m0`..`m5`, `canary`) |
| `/opt/ids/measure_image.sh` | image measurement script |
| `/etc/ids/ids.conf`, `/etc/ids/pool_pub.pem` | image defaults (override in `/data/ids.conf`), public verification key |
| `/etc/nftables.conf` | firewall rules with the `blocked` set |
| `/usr/lib/systemd/system/ids.service`, `data.mount` | service and the writable `/data` mount (enabled at boot) |
| `/etc/systemd/system/ids.service.d/hardening.conf` | service sandboxing |
| `/etc/sysctl.d/90-hardening.conf` | kernel hardening sysctls |
| `/etc/systemd/system/*` -> `/dev/null` | masks unneeded units (sshd, rpcbind, nfs, tcf-agent, syslog, ...) |
| user `ids` | system user, no shell, no home |

`files/ids-app` is the unused "Hello PetaLinux World" template stub; it is not in `SRC_URI`.

## Manual steps (not done by the recipe)

1. **Password hash.** `petalinuxbsp.conf` contains `<SHA512_HASH_OF_LAB_PASSWORD>` in the
   `useradd -p` line. Generate a hash with `openssl passwd -6`, put it in, and escape every `$` as
   `\$`. The lab password is shared with the team directly. Never commit the real password or
   hash; undo the edit before committing (`git diff` should show the placeholder).
2. **Rootfs menu.** Run `petalinux-config -c rootfs` and set:
   - Image Features -> init manager: **systemd** (the recipe needs `systemd` and `useradd`).
   - Enable the user packages listed in `user-rootfsconfig`: `gpio-demo`, `peekpoke`, `python3`,
     `python3-numpy`, `python3-paho-mqtt`, `nftables`, `openssl-bin`, `ids-app`.
   Without this the recipe's `RDEPENDS` are not in the image.
3. **Model pool (optional).** The image already boots with the signed factory pack baked in
   (`files/pool-factory/`, installed to `/opt/ids/pool-factory`); `idsd` logs
   `pack OK: /opt/ids/pool-factory` and runs without any extra step. Copy a signed pool to
   `/data/pool` (`pool/current`, `pool/v*`) on the target only if you want to test pack
   updates. Packs must be signed with the key matching `files/pool_pub.pem`; the private key
   (`keys/pool_priv.pem`) must never be committed.
