// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2024.1 (64-bit)
// Tool Version Limit: 2024.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2024 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// ctrl
// 0x00 : Control signals
//        bit 0  - ap_start (Read/Write/COH)
//        bit 1  - ap_done (Read/COR)
//        bit 2  - ap_idle (Read)
//        bit 3  - ap_ready (Read/COR)
//        bit 7  - auto_restart (Read/Write)
//        bit 9  - interrupt (Read)
//        others - reserved
// 0x04 : Global Interrupt Enable Register
//        bit 0  - Global Interrupt Enable (Read/Write)
//        others - reserved
// 0x08 : IP Interrupt Enable Register (Read/Write)
//        bit 0 - enable ap_done interrupt (Read/Write)
//        bit 1 - enable ap_ready interrupt (Read/Write)
//        others - reserved
// 0x0c : IP Interrupt Status Register (Read/TOW)
//        bit 0 - ap_done (Read/TOW)
//        bit 1 - ap_ready (Read/TOW)
//        others - reserved
// 0x10 : Data signal of score
//        bit 31~0 - score[31:0] (Read)
// 0x14 : Control signal of score
//        bit 0  - score_ap_vld (Read/COR)
//        others - reserved
// 0x20 : Data signal of attack
//        bit 7~0 - attack[7:0] (Read)
//        others  - reserved
// 0x24 : Control signal of attack
//        bit 0  - attack_ap_vld (Read/COR)
//        others - reserved
// 0x30 : Data signal of model_id
//        bit 31~0 - model_id[31:0] (Read)
// 0x34 : Control signal of model_id
//        bit 0  - model_id_ap_vld (Read/COR)
//        others - reserved
// 0x40 ~
// 0x7f : Memory 'x' (61 * 8b)
//        Word n : bit [ 7: 0] - x[4n]
//                 bit [15: 8] - x[4n+1]
//                 bit [23:16] - x[4n+2]
//                 bit [31:24] - x[4n+3]
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XQMLP_CTRL_ADDR_AP_CTRL       0x00
#define XQMLP_CTRL_ADDR_GIE           0x04
#define XQMLP_CTRL_ADDR_IER           0x08
#define XQMLP_CTRL_ADDR_ISR           0x0c
#define XQMLP_CTRL_ADDR_SCORE_DATA    0x10
#define XQMLP_CTRL_BITS_SCORE_DATA    32
#define XQMLP_CTRL_ADDR_SCORE_CTRL    0x14
#define XQMLP_CTRL_ADDR_ATTACK_DATA   0x20
#define XQMLP_CTRL_BITS_ATTACK_DATA   8
#define XQMLP_CTRL_ADDR_ATTACK_CTRL   0x24
#define XQMLP_CTRL_ADDR_MODEL_ID_DATA 0x30
#define XQMLP_CTRL_BITS_MODEL_ID_DATA 32
#define XQMLP_CTRL_ADDR_MODEL_ID_CTRL 0x34
#define XQMLP_CTRL_ADDR_X_BASE        0x40
#define XQMLP_CTRL_ADDR_X_HIGH        0x7f
#define XQMLP_CTRL_WIDTH_X            8
#define XQMLP_CTRL_DEPTH_X            61

