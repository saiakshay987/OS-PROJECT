#!/usr/bin/env bash
# os/buildroot/build.sh — build the hardened Buildroot IDS image from a clean clone of this repo (P4).
#
#   os/buildroot/build.sh configure   fast (seconds): fetch Buildroot if needed, check inputs, load ids_zynq_defconfig
#   os/buildroot/build.sh build       configure + full build (the long step) -> $OUT/images/{sdcard.img,uImage,zynq-zed.dtb,...}
#   os/buildroot/build.sh manifest    legal-info + package manifest (report/package_manifest_buildroot.csv)
#   os/buildroot/build.sh all         build + manifest
#
# Environment (all optional):
#   BUILDROOT_DIR  existing Buildroot 2025.02.19 tree (default $HOME/buildroot; downloaded there if absent)
#   OUT            output directory, outside the repo (default $HOME/br-ids)
#   JOBS           parallel jobs (default: nproc)
# Run it from anywhere; paths are resolved from this file's location. Never run as root.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
EXT=$REPO/os/buildroot/external
BUILDROOT_DIR=${BUILDROOT_DIR:-$HOME/buildroot}
OUT=${OUT:-$HOME/br-ids}
JOBS=${JOBS:-$(nproc)}
BR_VERSION=2025.02.19
mode=${1:-configure}

die() { echo "build.sh: $*" >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || die "do not run as root (Buildroot refuses)"

# 1. host tools (Fedora: dnf install ...; Debian/Ubuntu: apt install ...)
for t in gcc g++ make patch tar bzip2 gzip xz perl python3 wget unzip rsync bc cpio file openssl sed which; do
  command -v "$t" >/dev/null || die "missing host tool: $t"
done

# 2. repo inputs the image needs (post-build.sh copies them into the root filesystem)
[ -f "$REPO/keys/pool_pub.pem" ]         || die "keys/pool_pub.pem missing (release PUBLIC key)"
[ -f "$REPO/models/pool/manifest.sig" ]  || die "models/pool (signed factory pack) missing"
python3 "$REPO/common/modelpack.py" verify "$REPO/models/pool" "$REPO/keys/pool_pub.pem" \
  || die "factory pack does not verify against keys/pool_pub.pem; the image would refuse every model"

# 3. Buildroot itself (tarball release, not a git checkout)
if [ ! -f "$BUILDROOT_DIR/Makefile" ]; then
  echo ">> downloading Buildroot $BR_VERSION to $BUILDROOT_DIR"
  mkdir -p "$BUILDROOT_DIR"
  wget -O- "https://buildroot.org/downloads/buildroot-$BR_VERSION.tar.xz" | tar -xJ -C "$BUILDROOT_DIR" --strip-components=1
fi
grep -q "BR2_VERSION := $BR_VERSION" "$BUILDROOT_DIR/Makefile" || die "$BUILDROOT_DIR is not Buildroot $BR_VERSION"

MK=(make -C "$BUILDROOT_DIR" O="$OUT" BR2_EXTERNAL="$EXT")

configure() {
  # BR2_EXTERNAL must be an absolute path. The defconfig reaches ../../../kernel/ids.cfg relative to it, so keep the repo layout.
  "${MK[@]}" ids_zynq_defconfig
}

build() {
  configure
  # Long step: toolchain + kernel + U-Boot + Python/numpy + systemd. Needs about 15 GB free in $OUT and network for sources.
  # post-build.sh (os/buildroot/external/board/ids/post-build.sh) runs inside this: it installs the app, firewall, hardening,
  # read-only root, public key and factory pack from this repo into the root filesystem.
  "${MK[@]}" -j"$JOBS" 2>&1 | tee "$OUT/build.log"
  ls -l "$OUT"/images/sdcard.img "$OUT"/images/uImage "$OUT"/images/zynq-zed.dtb
}

manifest() {
  "${MK[@]}" legal-info
  # --no-print-directory: "make -C" otherwise prints "Entering directory" into the JSON (found in the 21 Nov clean-clone build)
  "${MK[@]}" --no-print-directory show-info > "$OUT/show-info.json"
  python3 "$REPO/os/buildroot/gen_manifest.py" "$OUT/show-info.json" "$OUT/build/packages-file-list.txt" \
    > "$REPO/report/package_manifest_buildroot.csv"
  cp "$OUT/legal-info/manifest.csv" "$REPO/report/licences-manifest.csv"
  echo ">> wrote report/package_manifest_buildroot.csv and report/licences-manifest.csv"
}

case "$mode" in
  configure) configure ;;
  build)     build ;;
  manifest)  manifest ;;
  all)       build; manifest ;;
  *) die "usage: $0 configure|build|manifest|all" ;;
esac

cat <<NOTE
Manual steps that remain (not done by this script):
  1. SIGNING: the factory pack in models/pool is already signed. A new pack version needs the release PRIVATE key (one laptop,
     keys_release/pool_priv.pem, never in git):  python3 common/modelpack.py sign <pool dir> keys_release/pool_priv.pem <version>
     then rebuild so post-build.sh copies it into the image.
  2. Boot in QEMU:  os/buildroot/qemu/boot_ids.sh   (needs qemu-system-arm; the QEMU-only DTB is made on first run).
  3. Real board: not done. No PYNQ-Z2 device tree, no persistent /data partition (tmpfs in this image), no bitstream flow.
NOTE
