#!/bin/bash
# Run ids_cosim from cosim/rtl: the HLS ROM files are loaded with $readmemh("./x.dat"),
# which is resolved relative to the current directory. ids_cosim.vcd is written there too.
# Usage: ./run.sh unix:/tmp/cosim/qemu-rport-_cosim@0 100000
cd "$(dirname "$0")/../rtl" && exec ../sc/ids_cosim "$@"
