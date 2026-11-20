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
#include "Vqmlp.h"
#include "soc/xilinx/zynq/xilinx-zynq.h"

#define NR_MASTERS	1
#define NR_DEVICES	1

/* Where the IP sits in the PL address space (GP0 window is 0x40000000-0x7fffffff). */
#define QMLP_BASE	0x43C00000ULL
#define QMLP_SIZE	0x10000ULL
/* qmlp_ctrl_s_axi has C_S_AXI_ADDR_WIDTH = 7 (registers at 0x00-0x7f). */
#define QMLP_ADDR_WIDTH	7

SC_MODULE(Top)
{
	iconnect<NR_MASTERS, NR_DEVICES> bus;
	xilinx_zynq zynq;
	sc_clock clk;                    /* 100 MHz, the HLS target period is 10 ns */
	sc_signal<bool> rst;             /* active high, for the Zynq PS model */
	sc_signal<bool> rst_n;           /* active low, for the IP and the bridge */
	sc_signal<bool> irq_unused;
	AXILiteSignals<QMLP_ADDR_WIDTH, 32> signals;
	tlm2axilite_bridge<QMLP_ADDR_WIDTH, 32> bridge;
	Vqmlp dut;                       /* Verilated Vitis HLS RTL */

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
		wait(20 * 10, SC_NS);
		rst_n.write(true);
	}

	Top(sc_module_name name, const char *sk_descr, sc_time quantum) :
		bus("bus"),
		zynq("zynq", sk_descr),
		clk("clk", sc_time(10, SC_NS)),
		rst("rst"),
		rst_n("rst_n"),
		irq_unused("irq_unused"),
		signals("signals"),
		bridge("bridge"),
		dut("dut")
	{
		m_qk.set_global_quantum(quantum);

		zynq.rst(rst);

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
	trace(trace_fp, *top, top->name());
	sc_trace(trace_fp, top->clk, "clk");
	sc_trace(trace_fp, top->rst_n, "rst_n");
	top->signals.Trace(trace_fp);

	sc_start();
	if (trace_fp) {
		sc_close_vcd_trace_file(trace_fp);
	}
	return 0;
}
