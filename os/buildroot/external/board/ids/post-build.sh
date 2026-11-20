#!/bin/sh
# Runs after the rootfs is assembled. $1 = target dir. Copies the app + security files from the repo (single source of truth).
set -e
T="$1"
R="$BR2_EXTERNAL_IDS_PATH/../../.."          # repo root (this tree lives in os/buildroot/external)
warn() { echo "post-build WARNING: $*" >&2; }

install -d "$T/opt/ids/pool-factory" "$T/etc/ids" "$T/etc/sysctl.d" "$T/data" \
           "$T/etc/systemd/system/ids.service.d" "$T/etc/systemd/system/multi-user.target.wants" \
           "$T/etc/systemd/network"

install -m 0644 "$R/app/appliance/idsd.py" "$R/app/appliance/fpga_regs.py" \
                "$R/common/qmlp.py" "$R/common/modelpack.py" "$T/opt/ids/"
install -m 0644 "$R/app/appliance/ids.conf"            "$T/etc/ids/ids.conf"
install -m 0644 "$R/security/nftables.conf"            "$T/etc/nftables.conf"
install -m 0644 "$R/security/90-hardening.sysctl.conf" "$T/etc/sysctl.d/90-hardening.conf"
install -m 0644 "$R/os/petalinux/ids.service"          "$T/etc/systemd/system/ids.service"
install -m 0644 "$R/security/ids.hardening.conf"       "$T/etc/systemd/system/ids.service.d/hardening.conf"
ln -sf ../ids.service "$T/etc/systemd/system/multi-user.target.wants/ids.service"

# DHCP on eth0 (QEMU's user network hands out 10.0.2.15)
cat > "$T/etc/systemd/network/20-eth0.network" <<'NET'
[Match]
Name=eth0 end0
[Network]
DHCP=yes
NET

# release public key + factory model pack (both come from other people's steps: warn, don't fail)
if [ -f "$R/keys/pool_pub.pem" ]; then install -m 0644 "$R/keys/pool_pub.pem" "$T/etc/ids/pool_pub.pem"
else warn "keys/pool_pub.pem missing: image will refuse every model pack"; fi
if ls "$R"/models/pool/*.npz >/dev/null 2>&1; then cp -r "$R"/models/pool/. "$T/opt/ids/pool-factory/"
else warn "models/pool missing: no factory model pack in the image"; fi

# /data: tmpfs in QEMU (no third partition). Updates are lost at power-off.
grep -qs ' /data ' "$T/etc/fstab" || echo 'tmpfs /data tmpfs nodev,nosuid,size=64M 0 0' >> "$T/etc/fstab"

# Firewall as its own unit: loaded once, early, BEFORE the network comes up (the repo's nftables.conf starts with
# 'flush ruleset', so it must not be re-run each time the detector restarts: that would empty the 'blocked' set).
cat > "$T/etc/systemd/system/nftables.service" <<'UNIT'
[Unit]
Description=Default-deny firewall (nftables)
DefaultDependencies=no
Before=network-pre.target sysinit.target
Wants=network-pre.target
Conflicts=shutdown.target
Before=shutdown.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/nftables.conf
[Install]
WantedBy=sysinit.target
UNIT
install -d "$T/etc/systemd/system/sysinit.target.wants"
ln -sf ../nftables.service "$T/etc/systemd/system/sysinit.target.wants/nftables.service"
# the detector requires the firewall (fails closed if it is missing) and no longer reloads the rules itself
cat > "$T/etc/systemd/system/ids.service.d/10-firewall.conf" <<'UNIT'
[Unit]
Requires=nftables.service
After=nftables.service
[Service]
ExecStartPre=
UNIT

# Fail-closed detector: stop retrying after 3 failed starts instead of looping forever
cat > "$T/etc/systemd/system/ids.service.d/20-restart.conf" <<'UNIT'
[Unit]
StartLimitIntervalSec=300
StartLimitBurst=3
[Service]
RestartSec=30
UNIT

# No LLMNR / mDNS listener on 5355
install -d "$T/etc/systemd/resolved.conf.d"
printf '[Resolve]\nLLMNR=no\nMulticastDNS=no\n' > "$T/etc/systemd/resolved.conf.d/10-no-llmnr.conf"

# read-only root: tmpfs for /var, ro on the boot command line
grep -q '^tmpfs /var ' "$T/etc/fstab" || echo 'tmpfs /var tmpfs nodev,nosuid,size=32M 0 0' >> "$T/etc/fstab"
if [ -f "$BINARIES_DIR/extlinux.conf" ]; then
    sed -i 's/ rw / ro /' "$BINARIES_DIR/extlinux.conf"
else
    echo "WARNING: extlinux.conf not found, boot partition still says rw"
fi

# fstab-ro: force the root entry read-only (the skeleton package keeps writing rw)
sed -i '/^\/dev\/root[[:space:]]/ s/\brw\b/ro/' "$T/etc/fstab"

# dropbear: no password logins (-s), no root logins (-w); the unit reads DROPBEAR_ARGS from /etc/default/dropbear
install -d "$T/etc/default"
echo 'DROPBEAR_ARGS="-s -w"' > "$T/etc/default/dropbear"
