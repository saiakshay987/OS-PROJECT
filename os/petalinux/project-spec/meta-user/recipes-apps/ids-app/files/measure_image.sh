#!/bin/sh
# bench/measure_image.sh <label> — run INSIDE an image after boot (PetaLinux, Buildroot, later stock); prints one CSV line.
# header: image,kernel,uptime_s,mem_used_mb,root_used_mb,processes,modules,listening_ports,packages,setuid_files,boot
img="$1"
up=$(cut -d' ' -f1 /proc/uptime)
memused=$(free -m | awk '/Mem:/{print $3}')
rootused=$(df -m / | awk 'NR==2{print $3}')
procs=$(ls -d /proc/[0-9]* | wc -l)
mods=$(wc -l < /proc/modules 2>/dev/null || echo 0)
ports=$( (ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null) | grep -cE 'LISTEN|^udp')
suid=$(find / -xdev -perm -4000 -type f 2>/dev/null | wc -l)
if   command -v dpkg >/dev/null; then pkgs=$(dpkg -l | grep -c '^ii')
elif command -v rpm  >/dev/null; then pkgs=$(rpm -qa | wc -l)
elif command -v opkg >/dev/null; then pkgs=$(opkg list-installed | wc -l)
else pkgs=NA; fi
sa=$(systemd-analyze 2>/dev/null | head -1 | tr ',' ';')
echo "$img,$(uname -r),$up,$memused,$rootused,$procs,$mods,$ports,$pkgs,$suid,\"$sa\""
