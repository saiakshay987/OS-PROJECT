#!/bin/bash
# Build ids_cosim: Xilinx's zynq_demo top level with the Verilated m0 `qmlp` IP attached.
# Usage: ./build.sh <path-to-systemctlm-cosim-demo>   (already built with `make zynq_demo`)
set -euo pipefail
DEMO=$(realpath "${1:?usage: build.sh <path-to-systemctlm-cosim-demo>}")
HERE=$(cd "$(dirname "$0")" && pwd)
RTL="$HERE/../rtl"
OBJ="$HERE/obj_dir"
export SYSTEMC_INCLUDE=${SYSTEMC_INCLUDE:-/usr/include}
export SYSTEMC_LIBDIR=${SYSTEMC_LIBDIR:-/usr/lib/x86_64-linux-gnu}

# 1. Verilate the RTL as SystemC (multi-bit ports become sc_bv, matching the bridge).
rm -rf "$OBJ"
( cd "$RTL" && verilator --sc --pins-bv 2 -Wno-fatal --output-split-cfuncs 500 \
    --top-module qmlp --Mdir "$OBJ" *.v )
make -C "$OBJ" -f Vqmlp.mk Vqmlp__ALL.a verilated.o > "$OBJ/make.log" 2>&1 || { tail -30 "$OBJ/make.log"; exit 1; }
ls "$OBJ/Vqmlp__ALL.a" "$OBJ/verilated.o" > /dev/null

# 2. Take the compile and link commands from the demo's own Makefile.
cd "$DEMO"
CC_CMD=$(make -B -n zynq_demo | grep -- ' -c -o zynq_demo.o zynq_demo.cc' | head -1)
LD_CMD=$(make -B -n zynq_demo | grep -- ' -o zynq_demo zynq_demo.o' | head -1)
[ -n "$CC_CMD" ] && [ -n "$LD_CMD" ] || { echo "could not extract commands from 'make -n zynq_demo'"; exit 1; }

# 3. Compile our top level (extra includes: Verilated model, library test-modules header).
CC_CMD=${CC_CMD/-c -o zynq_demo.o zynq_demo.cc/-I $OBJ -I /usr/share/verilator/include -I $DEMO/libsystemctlm-soc/tests -c -o $HERE/ids_cosim.o $HERE/ids_cosim.cc}
echo "$CC_CMD"; eval "$CC_CMD"

# 4. Link: demo objects, our top level, Verilated model.
LD_CMD=${LD_CMD/-o zynq_demo zynq_demo.o/-o $HERE/ids_cosim $HERE/ids_cosim.o $OBJ/verilated.o $OBJ/Vqmlp__ALL.a}
echo "$LD_CMD"; eval "$LD_CMD"
echo "built $HERE/ids_cosim"
