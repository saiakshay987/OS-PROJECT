# ml/qat.py — quantisation-aware training of small MLPs and export to the integer format in common/qmlp.py.  Owner: P3
import math, os, sys
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from qmlp import QMLP, FMLP
DEV = "cuda" if torch.cuda.is_available() else "cpu"

class QLinear(nn.Linear):
    def __init__(self, i, o, bits):
        super().__init__(i, o); self.Q = 2 ** (bits - 1) - 1 if bits > 1 else 1
    def scale(self): return self.weight.detach().abs().max().clamp_min(1e-8) / self.Q
    def wint(self): return torch.round(torch.clamp(self.weight / self.scale(), -self.Q, self.Q))
    def forward(self, x):
        wq = self.wint() * self.scale()
        return F.linear(x, self.weight + (wq - self.weight).detach(), self.bias)      # straight-through estimator

class QNet(nn.Module):
    """wbits = 0 means full precision (baseline)."""
    def __init__(self, n_in, hidden, wbits, abits):
        super().__init__()
        dims = [n_in] + list(hidden) + [1]; self.wbits, self.abits = wbits, abits
        mk = (lambda i, o: QLinear(i, o, wbits)) if wbits else nn.Linear
        self.fc = nn.ModuleList(mk(i, o) for i, o in zip(dims[:-1], dims[1:]))
        self.alpha = nn.Parameter(torch.full((len(hidden),), 3.0))                    # learned clipping level per layer
        self.L = 2 ** abits - 1 if abits else None
    def forward(self, x):
        for i, fc in enumerate(self.fc[:-1]):
            z = F.relu(fc(x))
            if self.L:
                al = self.alpha[i].abs() + 1e-3
                a = torch.minimum(z, al)
                x = a + (torch.round(a / al * self.L) * al / self.L - a).detach()
            else:
                x = z
        return self.fc[-1](x)[:, 0]

def train(X, y, hidden, wbits, abits, seed, epochs=15, frac=1.0, bs=512, lr=2e-3, log=None):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), int(frac * len(X)), replace=False)
    Xt = torch.tensor(X[idx], dtype=torch.float32, device=DEV) / 255.0
    yt = torch.tensor(y[idx], dtype=torch.float32, device=DEV)
    net = QNet(X.shape[1], hidden, wbits, abits).to(DEV)
    opt = torch.optim.Adam(net.parameters(), lr=lr); sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    for ep in range(epochs):
        perm = torch.randperm(len(Xt), device=DEV); tot = 0.0
        for i in range(0, len(Xt), bs):
            b = perm[i:i + bs]; loss = F.binary_cross_entropy_with_logits(net(Xt[b]), yt[b])
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(b)
        sched.step()
        if log: log(f"  epoch {ep + 1}/{epochs} loss {tot / len(Xt):.4f}")
    return net.eval()

def export(net, meta):
    """Trained QNet -> integer QMLP (or FMLP when wbits == 0)."""
    if not net.wbits:
        return FMLP([f.weight.detach().cpu().numpy() for f in net.fc], [f.bias.detach().cpu().numpy() for f in net.fc], 0.0, meta)
    layers, s_in = [], 1.0 / 255.0
    for i, fc in enumerate(net.fc):
        s = float(fc.scale()); W = fc.wint().detach().cpu().numpy().astype(np.int8)
        b = np.rint(fc.bias.detach().cpu().numpy().astype(np.float64) / (s * s_in)).astype(np.int64)
        if i == len(net.fc) - 1:
            layers.append({"W": W, "b": b, "M": 0, "SH": 1, "L": None}); break
        al = float(net.alpha[i].detach().abs() + 1e-3); k = s * s_in * net.L / al
        SH = int(min(40, max(1, 14 - math.floor(math.log2(k)))))            # keep M as a 15-bit multiplier
        layers.append({"W": W, "b": b, "M": int(round(k * 2 ** SH)), "SH": SH, "L": net.L})
        s_in = al / net.L
    return QMLP(layers, 0, meta)

def float_scores(net, X):
    with torch.no_grad():
        return torch.cat([net(torch.tensor(X[i:i + 8192], dtype=torch.float32, device=DEV) / 255.0)
                          for i in range(0, len(X), 8192)]).cpu().numpy()

def calibrate(model, Xv, yv, fpr):
    """Set the threshold so that the false-positive rate on benign validation records is `fpr`."""
    s = np.sort(model.score(Xv[yv == 0])); t = s[min(len(s) - 1, int(math.ceil((1 - fpr) * len(s))))]
    model.thr = int(t) if isinstance(model, QMLP) else float(t)

def metrics(model, X, y):
    p = model.predict(X); tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum())
    fn = int((~p & (y == 1)).sum()); tn = int((~p & (y == 0)).sum())
    pr = tp / max(1, tp + fp); rc = tp / max(1, tp + fn)
    return {"acc": (tp + tn) / len(y), "precision": pr, "recall": rc, "f1": 2 * pr * rc / max(1e-9, pr + rc), "fpr": fp / max(1, fp + tn)}
