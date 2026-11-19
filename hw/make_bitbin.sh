#!/bin/sh
# hw/make_bitbin.sh m0.bit  ->  m0.bit.bin (the format the Zynq FPGA manager loads). Needs bootgen from Vivado/Vitis.
set -e; b=$(basename "$1"); printf 'all: { %s }\n' "$1" > /tmp/bit.bif
bootgen -image /tmp/bit.bif -arch zynq -process_bitstream bin -w
ls -l "$1.bin"      # this file size / PCAP speed = the minimum possible swap time; write it in hw/NOTES.md
# on the board:  fpgautil -b /lib/firmware/ids/$b.bin -o /lib/firmware/ids/qmlp.dtbo ; cat /sys/class/fpga_manager/fpga0/state
