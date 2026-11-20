/*
 * Top level of the Zynq cosim example, modified for the IDS project:
 * the demo's debug device is replaced by the Verilated m0 `qmlp` IP
 * (Vitis HLS RTL, AXI4-Lite slave `ctrl`) at 0x43C00000.
 * Derived from Xilinx systemctlm-cosim-demo/zynq_demo.cc (MIT-style licence below).
 *
 * Copyright (c) 2014 Xilinx Inc.
 * Written by Edgar E. Iglesias
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#define SC_INCLUDE_DYNAMIC_PROCESSES

#include <inttypes.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>

#include "systemc.h"
#include "tlm_utils/simple_initiator_socket.h"
#include "tlm_utils/simple_target_socket.h"
#include "tlm_utils/tlm_quantumkeeper.h"

using namespace sc_core;
using namespace sc_dt;
using namespace std;

#include "trace.h"
#include "soc/interconnect/iconnect.h"
#include "tlm-bridges/tlm2axilite-bridge.h"
#include "test-modules/signals-axilite.h"
#include "tests/test-modules/memory.h"
#include "Vqmlp.h"
#include "soc/xilinx/zynq/xilinx-zynq.h"

#define NR_MASTERS	1
#define NR_DEVICES	2

/* Where the IP sits in the PL address space (GP0 window is 0x40000000-0x7fffffff). */
#define QMLP_BASE	0x43C00000ULL
#define QMLP_SIZE	0x10000ULL
/* qmlp_ctrl_s_axi has C_S_AXI_ADDR_WIDTH = 7 (registers at 0x00-0x7f). */
#define QMLP_ADDR_WIDTH	7
/* PL clock period. NOT the 10 ns HLS target: QEMU runs with -icount 7 and a 100 us sync quantum, so
   a 100 MHz clock would need 10000 simulated RTL cycles per quantum and the boot never finishes.
   10 us (as Xilinx's zynqmp_demo uses) keeps boot fast; one inference is ~343 cycles = ~3.4 ms.
   Override at build time with -DQMLP_CLK_NS=... */
#ifndef QMLP_CLK_NS
#define QMLP_CLK_NS	10000
#endif

SC_MODULE(Top)
{
	iconnect<NR_MASTERS, NR_DEVICES> bus;
	xilinx_zynq zynq;
	sc_clock clk;                    /* period QMLP_CLK_NS, see above */
	sc_signal<bool> rst;             /* active high, for the Zynq PS model */
	sc_signal<bool> rst_n;           /* active low, for the IP and the bridge */
	sc_signal<bool> irq_unused;
	AXILiteSignals<QMLP_ADDR_WIDTH, 32> signals;
	tlm2axilite_bridge<QMLP_ADDR_WIDTH, 32> bridge;
	Vqmlp dut;                       /* Verilated Vitis HLS RTL */
	/* Catch-all stub. iconnect sends every address that matches no mapped target (it prints
	   "DECODE ERROR!") to TARGET 0 at offset 0. The image's device tree has an AXI GPIO at
	   0x41200000 whose driver writes 0 and 0xFFFFFFFF at boot; with the IP as target 0 those writes
	   landed on AP_CTRL and started the IP with auto_restart (it read back 0x81). So this stub is
	   mapped FIRST (= target 0) and absorbs them. */
	memory gpio_stub;

	/* Debug signals for the waveform (VCD only; they do not drive anything).
	   ap_idle / ap_start / ap_done are internal to the RTL, so they are copied out of the Verilated model:
	   ap_idle = qmlp.ap_idle, ap_start = ctrl_s_axi.int_ap_start, ap_done = ap_CS_fsm[8] (qmlp.v: ap_done = state9). */
	sc_signal<bool> dbg_ap_idle, dbg_ap_start, dbg_ap_done;
	/* The clock is only dumped inside a short window, because a Linux boot is ~1600 s of simulated time
	   (3e8 clock edges). With IDS_COSIM_VCD_CLK=1 the window opens at the first AXI write (= the first record's
	   input) and stays open IDS_COSIM_VCD_CLK_CYCLES clock cycles (default 20000 = 0.2 s simulated). */
	sc_signal<bool> dbg_clk;
	bool win_enabled, win_open;
	uint64_t win_cycles, win_cycles_max;

	void dbg_clk_proc(void) {
		if (clk.read()) {	/* rising edge: window bookkeeping */
			if (win_enabled && !win_open && win_cycles == 0 && signals.awvalid.read())
				win_open = true;
			if (win_open && ++win_cycles > win_cycles_max)
				win_open = false;
		}
		dbg_clk.write(win_open ? clk.read() : false);
	}

	void dbg_state_proc(void) {	/* sampled on the falling edge, when the state of the last rising edge has settled */
		dbg_ap_idle.write(dut.qmlp__DOT__ap_idle & 1);
		dbg_ap_start.write(dut.qmlp__DOT__ctrl_s_axi_U__DOT__int_ap_start & 1);
		dbg_ap_done.write((dut.qmlp__DOT__ap_CS_fsm >> 8) & 1);
	}

	SC_HAS_PROCESS(Top);

	void pull_reset(void) {
		/* Pull the reset signal.  */
		rst.write(true);
		wait(1, SC_US);
		rst.write(false);
	}

	void pull_reset_n(void) {
		/* Active-low reset for the IP, held for 20 clock cycles. */
		rst_n.write(false);
		wait(20 * QMLP_CLK_NS, SC_NS);
		rst_n.write(true);
	}

	Top(sc_module_name name, const char *sk_descr, sc_time quantum) :
		bus("bus"),
		zynq("zynq", sk_descr),
		clk("clk", sc_time(QMLP_CLK_NS, SC_NS)),
		rst("rst"),
		rst_n("rst_n"),
		irq_unused("irq_unused"),
		signals("signals"),
		bridge("bridge"),
		dut("dut"),
		gpio_stub("gpio_stub", sc_time(1, SC_US), 0x10000),
		dbg_ap_idle("ap_idle"), dbg_ap_start("ap_start"), dbg_ap_done("ap_done"), dbg_clk("dbg_clk"),
		win_enabled(getenv("IDS_COSIM_VCD_CLK") != NULL), win_open(false), win_cycles(0),
		win_cycles_max(getenv("IDS_COSIM_VCD_CLK_CYCLES") ? strtoull(getenv("IDS_COSIM_VCD_CLK_CYCLES"), NULL, 10) : 20000)
	{
		m_qk.set_global_quantum(quantum);

		zynq.rst(rst);

		/* Target 0: the stub (also the destination of all decode errors). */
		bus.memmap(0x41200000ULL, 0x10000 - 1,
				ADDRMODE_RELATIVE, -1, gpio_stub.socket);

		/* Same mapping style as the demo's debug device (relative offsets). */
		bus.memmap(QMLP_BASE, QMLP_SIZE - 1,
				ADDRMODE_RELATIVE, -1, bridge.tgt_socket);

		zynq.m_axi_gp[0]->bind(*(bus.t_sk[0]));

		/* AXI4-Lite bridge <-> signals <-> RTL. */
		bridge.clk(clk);
		bridge.resetn(rst_n);
		signals.connect(bridge);

		dut.ap_clk(clk);
		dut.ap_rst_n(rst_n);
		dut.s_axi_ctrl_AWVALID(signals.awvalid);
		dut.s_axi_ctrl_AWREADY(signals.awready);
		dut.s_axi_ctrl_AWADDR(signals.awaddr);
		dut.s_axi_ctrl_WVALID(signals.wvalid);
		dut.s_axi_ctrl_WREADY(signals.wready);
		dut.s_axi_ctrl_WDATA(signals.wdata);
		dut.s_axi_ctrl_WSTRB(signals.wstrb);
		dut.s_axi_ctrl_BVALID(signals.bvalid);
		dut.s_axi_ctrl_BREADY(signals.bready);
		dut.s_axi_ctrl_BRESP(signals.bresp);
		dut.s_axi_ctrl_ARVALID(signals.arvalid);
		dut.s_axi_ctrl_ARREADY(signals.arready);
		dut.s_axi_ctrl_ARADDR(signals.araddr);
		dut.s_axi_ctrl_RVALID(signals.rvalid);
		dut.s_axi_ctrl_RREADY(signals.rready);
		dut.s_axi_ctrl_RDATA(signals.rdata);
		dut.s_axi_ctrl_RRESP(signals.rresp);
		dut.__SYM__interrupt(irq_unused);	/* Verilator renames the reserved word */
		/* awprot/arprot are driven by the bridge into unused signals
		   (the IP has no prot inputs). */

		/* Tie off any remaining unconnected signals.  */
		zynq.tie_off();

		SC_THREAD(pull_reset);
		SC_THREAD(pull_reset_n);

		SC_METHOD(dbg_clk_proc);
		sensitive << clk.posedge_event() << clk.negedge_event();
		dont_initialize();
		SC_METHOD(dbg_state_proc);
		sensitive << clk.negedge_event();
		dont_initialize();
	}

private:
	tlm_utils::tlm_quantumkeeper m_qk;
};

void usage(void)
{
	cout << "tlm socket-path sync-quantum-ns" << endl;
}

int sc_main(int argc, char* argv[])
{
	Top *top;
	uint64_t sync_quantum;
	sc_trace_file *trace_fp = NULL;

	if (argc < 3) {
		sync_quantum = 10000;
	} else {
		sync_quantum = strtoull(argv[2], NULL, 10);
	}

	Verilated::commandArgs(argc, argv);
	sc_set_time_resolution(1, SC_PS);

	top = new Top("top", argv[1], sc_time((double) sync_quantum, SC_NS));

	if (argc < 3) {
		sc_start(1, SC_PS);
		sc_stop();
		usage();
		exit(EXIT_FAILURE);
	}

	trace_fp = sc_create_vcd_trace_file("ids_cosim");
	/* The demo traced the whole Zynq model plus our clock: ~28 MB/s, 18 GB in ten minutes during a
	   Linux boot. Only trace reset, the AXI-Lite signals and the three ap_* debug signals (they change only on
	   real activity). The clock is dumped only in a short window, and only on request: IDS_COSIM_VCD_CLK=1. */
	sc_trace(trace_fp, top->rst_n, "rst_n");
	sc_trace(trace_fp, top->dbg_ap_idle, "ap_idle");
	sc_trace(trace_fp, top->dbg_ap_start, "ap_start");
	sc_trace(trace_fp, top->dbg_ap_done, "ap_done");
	if (getenv("IDS_COSIM_VCD_CLK"))
		sc_trace(trace_fp, top->dbg_clk, "clk");
	top->signals.Trace(trace_fp);

	sc_start();
	if (trace_fp) {
		sc_close_vcd_trace_file(trace_fp);
	}
	return 0;
}
