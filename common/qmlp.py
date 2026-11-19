# common/qmlp.py — integer-only inference of a quantised MLP. THE reference for the ARM backend and the FPGA block.
# layer i:  acc = W_i · x + b_i   (all integers)
#           hidden:  x_next = clip( (acc * M_i + 2^(SH_i-1)) >> SH_i , 0, L_i )     L_i = 2^act_bits - 1
#           last:    score = acc ;  attack  <=>  score > thr
import hashlib, json
import numpy as np

class QMLP:
    def __init__(self, layers, thr=0, meta=None):
        self.layers, self.thr, self.meta = layers, int(thr), dict(meta or {})

    def score(self, X):
        x = np.asarray(X, dtype=np.int64)
        for ly in self.layers:
            acc = x @ ly["W"].T.astype(np.int64) + ly["b"]
            if ly["L"] is None:
                return acc[:, 0]
            x = np.clip((acc * ly["M"] + (1 << (ly["SH"] - 1))) >> ly["SH"], 0, ly["L"])

    def margin(self, X): return self.score(X) - self.thr          # > 0 means 'attack'
    def predict(self, X): return self.margin(X) > 0

    def save(self, path):
        d = {"thr": self.thr, "meta": json.dumps(self.meta), "n": len(self.layers)}
        for i, ly in enumerate(self.layers):
            d[f"W{i}"], d[f"b{i}"] = ly["W"].astype(np.int8), ly["b"].astype(np.int64)
            d[f"q{i}"] = np.array([ly["M"], ly["SH"], -1 if ly["L"] is None else ly["L"]], np.int64)
        np.savez(path, **d)

    @staticmethod
    def load(path):
        z = np.load(path, allow_pickle=False)
        layers = []
        for i in range(int(z["n"])):
            M, SH, L = (int(v) for v in z[f"q{i}"])
            layers.append({"W": z[f"W{i}"], "b": z[f"b{i}"], "M": M, "SH": SH, "L": None if L < 0 else L})
        return QMLP(layers, int(z["thr"]), json.loads(str(z["meta"])))

class FMLP:
    """Full-precision baseline (float32) with the same interface, for comparisons only."""
    def __init__(self, Ws, bs, thr=0.0, meta=None):
        self.Ws, self.bs, self.thr, self.meta = Ws, bs, float(thr), dict(meta or {})
    def score(self, X):
        x = np.asarray(X, np.float32) / 255.0
        for i, (W, b) in enumerate(zip(self.Ws, self.bs)):
            x = x @ W.T + b
            if i < len(self.Ws) - 1: x = np.maximum(x, 0)
        return x[:, 0]
    def margin(self, X): return self.score(X) - self.thr
    def predict(self, X): return self.margin(X) > 0
    def save(self, path):
        np.savez(path, n=len(self.Ws), thr=self.thr, meta=json.dumps(self.meta),
                 **{f"W{i}": W for i, W in enumerate(self.Ws)}, **{f"b{i}": b for i, b in enumerate(self.bs)})
    @staticmethod
    def load(path):
        z = np.load(path, allow_pickle=False); n = int(z["n"])
        return FMLP([z[f"W{i}"] for i in range(n)], [z[f"b{i}"] for i in range(n)], float(z["thr"]), json.loads(str(z["meta"])))

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""): h.update(chunk)
    return h.hexdigest()
