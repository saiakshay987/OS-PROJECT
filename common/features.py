# common/features.py — THE contract for feature vectors. Training, attacks, the appliance and the FPGA all follow this file.
# Input: UNSW-NB15 'training-set' / 'testing-set' CSV columns. Output: N_IN unsigned bytes per connection record.
import json
import numpy as np

NUM = ["dur", "spkts", "dpkts", "sbytes", "dbytes", "rate", "sttl", "dttl", "sload", "dload", "sloss", "dloss",
       "sinpkt", "dinpkt", "sjit", "djit", "swin", "dwin", "tcprtt", "synack", "ackdat", "smean", "dmean",
       "trans_depth", "response_body_len", "ct_srv_src", "ct_state_ttl", "ct_dst_ltm", "ct_src_dport_ltm",
       "ct_dst_sport_ltm", "ct_dst_src_ltm", "is_ftp_login", "ct_ftp_cmd", "ct_flw_http_mthd", "ct_src_ltm",
       "ct_srv_dst", "is_sm_ips_ports"]            # stcpb/dtcpb (random TCP sequence numbers) are dropped
CATS = {"proto": ["tcp", "udp", "arp", "ospf", "icmp", "igmp", "rtp", "sctp"],
        "service": ["-", "dns", "http", "smtp", "ftp-data", "ftp", "ssh", "pop3"],
        "state": ["FIN", "INT", "CON", "REQ", "RST"]}          # each gets one extra 'other' column
SHORTCUTS = ["sttl", "dttl", "ct_state_ttl"]      # TTL artefacts of the testbed; set DROP_SHORTCUTS to zero them
N_NUM = len(NUM)
N_CAT = sum(len(v) + 1 for v in CATS.values())
N_IN = N_NUM + N_CAT                              # 37 + 24 = 61 bytes per record
IDX = {n: i for i, n in enumerate(NUM)}

def split_raw(df):
    """DataFrame -> (R float64 (N, N_NUM) raw numeric values, C uint8 (N, N_CAT) one-hot 0/255)."""
    missing = [c for c in NUM + list(CATS) if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing columns {missing}; use the UNSW-NB15 training-set/testing-set files")
    R = df[NUM].to_numpy(dtype=np.float64)
    blocks = []
    for col, vals in CATS.items():
        s = df[col].astype(str).str.strip()
        b = np.zeros((len(df), len(vals) + 1), np.uint8)
        known = np.zeros(len(df), bool)
        for j, v in enumerate(vals):
            hit = (s == v).to_numpy(); b[hit, j] = 255; known |= hit
        b[~known, len(vals)] = 255
        blocks.append(b)
    return R, np.hstack(blocks)

def fit_scaler(R):
    """Per-feature scale = 99.9th percentile of log1p(value), so a few huge outliers don't flatten everything."""
    lm = np.percentile(np.log1p(np.clip(R, 0, None)), 99.9, axis=0)
    return {"logmax": np.maximum(lm, 1e-6).tolist(), "num": NUM}

def encode(R, C, scaler, drop_shortcuts=False):
    """(R, C) -> uint8 (N, N_IN). Numeric: round(255 * min(1, log1p(v) / logmax)). Categorical: 0 or 255."""
    lm = np.asarray(scaler["logmax"])
    q = np.rint(255.0 * np.clip(np.log1p(np.clip(R, 0, None)) / lm, 0.0, 1.0)).astype(np.uint8)
    if drop_shortcuts:
        q[:, [IDX[n] for n in SHORTCUTS]] = 0
    return np.hstack([q, C])

def save_scaler(s, path): json.dump(s, open(path, "w"))
def load_scaler(path): return json.load(open(path))

# ---------------- what an attacker can change without breaking the attack (our assumption, state it in the report) ----
# Each knob is a multiplier on a raw quantity the SENDER controls. Everything else in the record stays fixed.
KNOBS = [("dur", 1.0, 8.0),       # slow the connection down (never faster than the real attack)
         ("sbytes", 1.0, 4.0),    # pad packets with junk bytes
         ("spkts", 1.0, 3.0),     # split into / add extra packets
         ("sinpkt", 0.5, 4.0),    # change spacing between sent packets
         ("sjit", 0.5, 4.0)]      # change jitter
N_KNOBS = len(KNOBS)
KLO = np.array([k[1] for k in KNOBS]); KHI = np.array([k[2] for k in KNOBS])

def apply_knobs(R, K):
    """R (N, N_NUM) raw records, K (N, N_KNOBS) multipliers -> modified copy with dependent features kept consistent."""
    K = np.clip(K, KLO, KHI); R = R.copy()
    dur, sb, sp, si, sj = (K[:, i] for i in range(N_KNOBS))
    pk_old = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]
    R[:, IDX["dur"]] *= dur
    R[:, IDX["sbytes"]] = np.rint(R[:, IDX["sbytes"]] * sb)
    R[:, IDX["spkts"]] = np.rint(R[:, IDX["spkts"]] * sp)
    R[:, IDX["sinpkt"]] *= si
    R[:, IDX["sjit"]] *= sj
    pk_new = R[:, IDX["spkts"]] + R[:, IDX["dpkts"]]
    R[:, IDX["rate"]] *= np.where(pk_old > 0, pk_new / np.maximum(pk_old, 1), 1.0) / dur     # packets per second
    R[:, IDX["sload"]] *= sb / dur                                                           # source bits per second
    R[:, IDX["smean"]] = np.rint(R[:, IDX["smean"]] * sb / sp)                               # mean source packet size
    R[:, IDX["dload"]] /= dur                                                                # same reply, longer time
    return R
