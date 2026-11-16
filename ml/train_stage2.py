# ml/train_stage2.py — stage 2 (laptop GPU): a larger full-precision model that names the attack category.  Owner: P3
# usage: python ml/train_stage2.py [--epochs 20]      -> models/stage2.pt
import argparse, os, sys
import numpy as np, torch, torch.nn as nn
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from features import encode, load_scaler
ap = argparse.ArgumentParser(); ap.add_argument("--data", default="data/unsw_prep.npz"); ap.add_argument("--out", default="models")
ap.add_argument("--epochs", type=int, default=20); a = ap.parse_args()
dev = "cuda" if torch.cuda.is_available() else "cpu"
z = np.load(a.data); sc = load_scaler(os.path.join(a.out, "scaler.json")); cats = [str(c) for c in z["cats"]]
Xtr = torch.tensor(encode(z["R_def"], z["C_def"], sc), dtype=torch.float32, device=dev) / 255; ytr = torch.tensor(z["cat_def"], dtype=torch.long, device=dev)
Xte = torch.tensor(encode(z["R_test"], z["C_test"], sc), dtype=torch.float32, device=dev) / 255; yte = torch.tensor(z["cat_test"], dtype=torch.long, device=dev)
def make(n_in, n_out): return nn.Sequential(nn.Linear(n_in, 512), nn.ReLU(), nn.Linear(512, 256), nn.ReLU(), nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, n_out))
torch.manual_seed(0); net = make(Xtr.shape[1], len(cats)).to(dev); opt = torch.optim.Adam(net.parameters(), 1e-3)
w = (1.0 / torch.bincount(ytr, minlength=len(cats)).float().clamp_min(1)) ** 0.5; lossf = nn.CrossEntropyLoss(weight=w / w.mean())
for ep in range(a.epochs):
    perm = torch.randperm(len(Xtr), device=dev)
    for i in range(0, len(Xtr), 1024):
        b = perm[i:i + 1024]; loss = lossf(net(Xtr[b]), ytr[b]); opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad(): acc = (net(Xte).argmax(1) == yte).float().mean().item()
    print(f"epoch {ep + 1}: loss {loss.item():.3f} test acc {acc:.3f}")
torch.save({"state": net.state_dict(), "cats": cats, "n_in": Xtr.shape[1]}, os.path.join(a.out, "stage2.pt"))
print("saved", os.path.join(a.out, "stage2.pt"), "on", dev)
