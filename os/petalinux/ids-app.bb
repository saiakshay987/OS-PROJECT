# project-spec/meta-user/recipes-apps/ids-app/ids-app.bb     (petalinux-create apps --template install -n ids-app --enable)
# Copy into files/: idsd.py fpga_regs.py ids.conf (app/appliance), qmlp.py modelpack.py (common), ids.service,
#                   pool_pub.pem (PUBLIC key only), and the signed pack folder as pool-factory/
SUMMARY = "Rotating-model intrusion detector"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://idsd.py file://fpga_regs.py file://qmlp.py file://modelpack.py file://ids.conf \
           file://ids.service file://pool_pub.pem file://pool-factory"
S = "${WORKDIR}"
inherit systemd useradd
SYSTEMD_SERVICE:${PN} = "ids.service"
SYSTEMD_AUTO_ENABLE = "enable"
USERADD_PACKAGES = "${PN}"
USERADD_PARAM:${PN} = "--system --no-create-home --shell /sbin/nologin ids"
do_install() {
    install -d ${D}/opt/ids/pool-factory ${D}${systemd_system_unitdir} ${D}${sysconfdir}/ids
    install -m 0644 ${S}/idsd.py ${S}/fpga_regs.py ${S}/qmlp.py ${S}/modelpack.py ${D}/opt/ids/
    install -m 0644 ${S}/pool-factory/* ${D}/opt/ids/pool-factory/
    install -m 0644 ${S}/ids.conf ${S}/pool_pub.pem ${D}${sysconfdir}/ids/
    install -m 0644 ${S}/ids.service ${D}${systemd_system_unitdir}/
}
FILES:${PN} += "/opt/ids ${systemd_system_unitdir}"
RDEPENDS:${PN} += "python3 python3-numpy python3-paho-mqtt nftables openssl-bin"
