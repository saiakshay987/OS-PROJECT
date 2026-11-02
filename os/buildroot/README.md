# Buildroot (P4)

Commit only this BR2_EXTERNAL tree and the defconfig, never `output/`.

```
os/buildroot/external/                      (BR2_EXTERNAL tree — this is what you commit)
├── external.desc                           name: VOICE
├── external.mk                             include $(sort $(wildcard $(BR2_EXTERNAL_VOICE_PATH)/package/*/*.mk))
├── Config.in                               source "$BR2_EXTERNAL_VOICE_PATH/package/voice-app/Config.in"
├── configs/pynqz2_voice_defconfig          ← make savedefconfig output
├── board/pynqz2/
│   ├── ps7_init_gpl.c / .h                 ← from P1's .xsa (it's a zip: unzip -l voice_fe.xsa)
│   ├── zynq-pynqz2.dts                     ← start from zynq-zed.dts, console on UART0, + P1's dtsi
│   ├── linux-voice.cfg                     ← P1's kernel fragment
│   ├── rootfs-overlay/                     ← /etc/nftables.conf, sshd/dropbear config, app files, units
│   └── post-build.sh
└── package/voice-app/                      ← Config.in + voice-app.mk installing app/board/*
```
