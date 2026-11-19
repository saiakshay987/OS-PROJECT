# os/buildroot/ (P4) — commit only this BR2_EXTERNAL tree and the defconfig, never `output/`
```
os/buildroot/external/
├── external.desc                 name: IDS
├── external.mk                   include $(sort $(wildcard $(BR2_EXTERNAL_IDS_PATH)/package/*/*.mk))
├── Config.in                     source "$BR2_EXTERNAL_IDS_PATH/package/ids-app/Config.in"
├── configs/ids_zynq_defconfig    <- 'make savedefconfig' output
├── board/ids/
│   ├── linux-ids.cfg             <- copy of kernel/ids.cfg
│   ├── rootfs-overlay/           <- /etc/nftables.conf, /etc/ids/*, /opt/ids/*, systemd unit, sysctl file
│   └── post-build.sh             <- creates the 'ids' user, enables the service
└── package/ids-app/              <- Config.in + ids-app.mk installing app/appliance/* and common/{qmlp,modelpack}.py
```
Packages to select: python3, python-numpy, python-paho-mqtt, nftables, openssl (binary), systemd or BusyBox init, dropbear.
