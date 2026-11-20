# project-spec/meta-user/recipes-apps/ids-app/ids-app.bb     (petalinux-create apps --template install -n ids-app --enable)
# Copy into files/: idsd.py fpga_regs.py ids.conf (app/appliance), qmlp.py modelpack.py (common), ids.service,
#                   pool_pub.pem (PUBLIC key only), and the signed pack folder as pool-factory/
SUMMARY = "Rotating-model intrusion detector"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://idsd.py file://fpga_regs.py file://qmlp.py file://modelpack.py file://ids.conf \
           file://ids.service file://pool_pub.pem file://pool-factory file://nftables.conf file://data.mount \
           file://ids.hardening.conf file://90-hardening.sysctl.conf file://measure_image.sh"
S = "${WORKDIR}"
inherit systemd useradd
SYSTEMD_SERVICE:${PN} = "ids.service data.mount"
SYSTEMD_AUTO_ENABLE = "enable"
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --no-create-home --shell /sbin/nologin ids"
do_install() {
    install -d ${D}/opt/ids/pool-factory ${D}${systemd_system_unitdir} ${D}${sysconfdir}/ids
    install -m 0644 ${S}/idsd.py ${S}/fpga_regs.py ${S}/qmlp.py ${S}/modelpack.py ${D}/opt/ids/
    install -m 0644 ${S}/pool-factory/* ${D}/opt/ids/pool-factory/
    install -m 0644 ${S}/ids.conf ${S}/pool_pub.pem ${D}${sysconfdir}/ids/
    install -m 0644 ${S}/ids.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${S}/nftables.conf ${D}${sysconfdir}/nftables.conf
    install -m 0644 ${S}/data.mount ${D}${systemd_system_unitdir}/data.mount
    install -d ${D}/data
    install -d ${D}${sysconfdir}/systemd/system/ids.service.d
    install -m 0644 ${S}/ids.hardening.conf ${D}${sysconfdir}/systemd/system/ids.service.d/hardening.conf
    install -d ${D}${sysconfdir}/sysctl.d
    install -m 0644 ${S}/90-hardening.sysctl.conf ${D}${sysconfdir}/sysctl.d/90-hardening.conf
    install -m 0755 ${S}/measure_image.sh ${D}/opt/ids/measure_image.sh
    # Mask unneeded units (symlink to /dev/null)
    install -d ${D}${sysconfdir}/systemd/system
    for u in inetd.busybox.service rpcbind.service rpcbind.socket nfs-statd.service nfsserver.service \
             nfs-server.service nfs-mountd.service proc-fs-nfsd.mount tcf-agent.service \
             busybox-klogd.service busybox-syslog.service syslog.socket getty@tty1.service \
             systemd-resolved.service systemd-userdbd.service systemd-userdbd.socket \
             sshd.socket sshd.service; do
        ln -sf /dev/null ${D}${sysconfdir}/systemd/system/$u
    done
}
FILES:${PN} += "/opt/ids ${systemd_system_unitdir}"
FILES:${PN} += "/data"
FILES:${PN} += "${sysconfdir}/systemd/system/ids.service.d ${sysconfdir}/sysctl.d"
FILES:${PN} += "${sysconfdir}/systemd/system/*.service ${sysconfdir}/systemd/system/*.socket ${sysconfdir}/systemd/system/*.mount"
RDEPENDS:${PN} += "python3 python3-numpy python3-paho-mqtt nftables openssl-bin"
