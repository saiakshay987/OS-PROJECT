#!/bin/sh
# bench/stock_offline.sh pynq_z2_v3.1.img — measure the STOCK PYNQ image without a board (needs sudo, Linux host).
set -e
ls -l "$1"                                             # IMAGE SIZE (raw file)
LOOP=$(sudo losetup -Pf --show "$1"); lsblk "$LOOP"    # p1 = boot (FAT), p2 = rootfs (ext4)
sudo mkdir -p /mnt/stock_boot /mnt/stock_root
sudo mount -o ro "${LOOP}p1" /mnt/stock_boot; sudo mount -o ro "${LOOP}p2" /mnt/stock_root
ls -l /mnt/stock_boot                                  # kernel image size
sudo du -sx --block-size=1M /mnt/stock_root            # ROOTFS SIZE (used)
grep -c '^Package:' /mnt/stock_root/var/lib/dpkg/status            # PACKAGE COUNT
ls /mnt/stock_root/etc/systemd/system/multi-user.target.wants/ | wc -l   # services enabled at boot
sudo find /mnt/stock_root -xdev -perm -4000 -type f | wc -l       # setuid programs
sudo umount /mnt/stock_boot /mnt/stock_root; sudo losetup -d "$LOOP"
