#!/usr/bin/env python3
"""Package manifest of the Buildroot image (P4).
usage: make -C <buildroot> O=<out> show-info > show-info.json
       python3 os/buildroot/gen_manifest.py show-info.json <out>/build/packages-file-list.txt > report/package_manifest_buildroot.csv
One row per non-virtual *target* package Buildroot builds for this configuration. Column in_rootfs is "yes" when the package
put at least one file into the target root filesystem (first field of packages-file-list.txt)."""
import csv, json, sys
info = json.load(open(sys.argv[1]))
in_rootfs = {l.split(",")[0] for l in open(sys.argv[2]) if l.strip()}
w = csv.writer(sys.stdout, lineterminator="\n")
w.writerow(["package", "version", "licence", "redistributable", "in_rootfs", "source_archive"])
for name in sorted(k for k, v in info.items() if v.get("type") == "target" and not v.get("virtual")):
    v = info[name]
    src = ";".join(d.get("source", "") for d in v.get("downloads", []))
    w.writerow([name, v.get("version", ""), v.get("licenses") or "", v.get("redistributable", ""),
                "yes" if name in in_rootfs else "no", src])
