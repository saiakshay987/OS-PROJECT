// Check R: drive the Vitis HLS generated `qmlp` RTL (m0) through its AXI4-Lite
// slave in Verilator, with the same vectors the HLS C-sim used.
//
// Build/run: see cosim/NOTES.md (run from cosim/rtl so $readmemh finds the .dat files).
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include "Vqmlp.h"
#include "verilated.h"
#include "xqmlp_hw.h"

#ifndef N_IN
#define N_IN 61
#endif
static const int MODEL_ID_EXPECTED = 0;  // hw/hls/build/m0/qmlp.h: MODEL_ID
static const long long THR = 1;          // hw/hls/build/m0/qmlp.h: THR (attack = score > THR)

static Vqmlp *top;
static uint64_t cycles = 0;

// Required by Verilated models that use $time (the HLS RTL does).
double sc_time_stamp() { return (double)cycles; }

// One clock cycle. Inputs are already set; outputs are sampled by the caller
// BEFORE this call (i.e. before the rising edge), which is what the AXI
// handshake rule needs.
static void tick() {
    top->ap_clk = 0;
    top->eval();
    top->ap_clk = 1;
    top->eval();
    cycles++;
}
static void settle() {  // propagate combinational outputs after changing inputs
    top->ap_clk = 0;
    top->eval();
}

static const int TIMEOUT = 200;

static bool axil_write(uint32_t addr, uint32_t data) {
    top->s_axi_ctrl_AWADDR = addr;
    top->s_axi_ctrl_WDATA = data;
    top->s_axi_ctrl_WSTRB = 0xF;
    bool aw_done = false, w_done = false;
    for (int t = 0; t < TIMEOUT && !(aw_done && w_done); t++) {
        top->s_axi_ctrl_AWVALID = !aw_done;
        top->s_axi_ctrl_WVALID = !w_done;
        settle();
        bool aw_hs = top->s_axi_ctrl_AWVALID && top->s_axi_ctrl_AWREADY;
        bool w_hs = top->s_axi_ctrl_WVALID && top->s_axi_ctrl_WREADY;
        tick();  // handshake happens on this rising edge
        if (aw_hs) aw_done = true;
        if (w_hs) w_done = true;
    }
    top->s_axi_ctrl_AWVALID = 0;
    top->s_axi_ctrl_WVALID = 0;
    if (!(aw_done && w_done)) { printf("TIMEOUT: write address/data 0x%02x\n", addr); return false; }
    top->s_axi_ctrl_BREADY = 1;
    for (int t = 0; t < TIMEOUT; t++) {
        settle();
        bool b_hs = top->s_axi_ctrl_BVALID && top->s_axi_ctrl_BREADY;
        int resp = top->s_axi_ctrl_BRESP;
        tick();
        if (b_hs) {
            top->s_axi_ctrl_BREADY = 0;
            if (resp != 0) { printf("BRESP=%d on write 0x%02x\n", resp, addr); return false; }
            return true;
        }
    }
    top->s_axi_ctrl_BREADY = 0;
    printf("TIMEOUT: BVALID after write 0x%02x\n", addr);
    return false;
}

static bool axil_read(uint32_t addr, uint32_t &data) {
    top->s_axi_ctrl_ARADDR = addr;
    bool ar_done = false;
    for (int t = 0; t < TIMEOUT && !ar_done; t++) {
        top->s_axi_ctrl_ARVALID = 1;
        settle();
        bool ar_hs = top->s_axi_ctrl_ARVALID && top->s_axi_ctrl_ARREADY;
        tick();
        if (ar_hs) ar_done = true;
    }
    top->s_axi_ctrl_ARVALID = 0;
    if (!ar_done) { printf("TIMEOUT: ARREADY for read 0x%02x\n", addr); return false; }
    top->s_axi_ctrl_RREADY = 1;
    for (int t = 0; t < TIMEOUT; t++) {
        settle();
        bool r_hs = top->s_axi_ctrl_RVALID && top->s_axi_ctrl_RREADY;
        uint32_t d = top->s_axi_ctrl_RDATA;
        int resp = top->s_axi_ctrl_RRESP;
        tick();
        if (r_hs) {
            top->s_axi_ctrl_RREADY = 0;
            data = d;
            if (resp != 0) { printf("RRESP=%d on read 0x%02x\n", resp, addr); return false; }
            return true;
        }
    }
    top->s_axi_ctrl_RREADY = 0;
    printf("TIMEOUT: RVALID for read 0x%02x\n", addr);
    return false;
}

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    const char *vec_path = argc > 1 ? argv[1] : "vectors.txt";
    FILE *f = fopen(vec_path, "r");
    if (!f) { printf("cannot open %s\n", vec_path); return 2; }

    top = new Vqmlp;
    top->s_axi_ctrl_AWVALID = top->s_axi_ctrl_WVALID = top->s_axi_ctrl_ARVALID = 0;
    top->s_axi_ctrl_BREADY = top->s_axi_ctrl_RREADY = 0;
    top->s_axi_ctrl_AWADDR = top->s_axi_ctrl_ARADDR = 0;
    top->s_axi_ctrl_WDATA = 0;
    top->s_axi_ctrl_WSTRB = 0;

    top->ap_rst_n = 0;  // active low
    for (int i = 0; i < 20; i++) tick();
    top->ap_rst_n = 1;
    for (int i = 0; i < 5; i++) tick();

    uint32_t v = 0;
    if (!axil_read(XQMLP_CTRL_ADDR_AP_CTRL, v)) return 1;
    printf("AP_CTRL after reset = 0x%08x (ap_idle bit2 %s)\n", v, (v & 4) ? "set" : "NOT SET");
    bool idle_ok = (v & 4) != 0;

    int n = 0, bad = 0, errs = 0;
    while (true) {
        unsigned char x[N_IN];
        int ok = 1, t;
        for (int i = 0; i < N_IN; i++) {
            if (fscanf(f, "%d", &t) != 1) { ok = 0; break; }
            x[i] = (unsigned char)t;
        }
        long long want;
        if (!ok || fscanf(f, "%lld", &want) != 1) break;
        n++;

        bool good = true;
        // 61 bytes -> 16 words, little-endian, zero padded (see cosim/NOTES.md)
        for (int w = 0; w < 16 && good; w++) {
            uint32_t word = 0;
            for (int b = 0; b < 4; b++) {
                int idx = 4 * w + b;
                if (idx < N_IN) word |= (uint32_t)x[idx] << (8 * b);
            }
            good = axil_write(XQMLP_CTRL_ADDR_X_BASE + 4 * w, word);
        }
        if (good) good = axil_write(XQMLP_CTRL_ADDR_AP_CTRL, 1);  // ap_start
        bool done = false;
        for (int p = 0; good && p < 100000 && !done; p++) {
            good = axil_read(XQMLP_CTRL_ADDR_AP_CTRL, v);
            if (good && (v & 2)) done = true;  // ap_done
        }
        if (good && !done) { printf("vec %d: TIMEOUT waiting for ap_done\n", n); good = false; }
        uint32_t score_u = 0, attack = 0, mid = 0;
        if (good) good = axil_read(XQMLP_CTRL_ADDR_SCORE_DATA, score_u);
        if (good) good = axil_read(XQMLP_CTRL_ADDR_ATTACK_DATA, attack);
        if (good) good = axil_read(XQMLP_CTRL_ADDR_MODEL_ID_DATA, mid);
        if (!good) { errs++; bad++; if (errs >= 3) { printf("too many bus errors, stopping\n"); break; } continue; }

        int32_t score = (int32_t)score_u;
        bool want_attack = want > THR;
        if (score != (int32_t)want || (attack & 0xff) != (uint32_t)want_attack || (int)mid != MODEL_ID_EXPECTED) {
            if (bad++ < 5)
                printf("MISMATCH vec %d: got score=%d attack=%u id=%u, want score=%lld attack=%d id=%d\n",
                       n, score, attack & 0xff, mid, want, (int)want_attack, MODEL_ID_EXPECTED);
        }
    }
    fclose(f);
    bool pass = !bad && n > 0 && idle_ok;
    printf("%d vectors, %d mismatches (%llu clock cycles) -> %s\n", n, bad, (unsigned long long)cycles,
           pass ? "PASS" : "FAIL");
    delete top;
    return pass ? 0 : 1;
}
