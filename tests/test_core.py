import os, pathlib, shutil, subprocess, sys
import numpy as np, pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "common"))
from features import N_IN, N_NUM, IDX, KLO, KHI, apply_knobs, encode, fit_scaler
from qmlp import QMLP
import modelpack

def tiny_model(seed, n_in=N_IN):
    r = np.random.default_rng(seed)
    L = [{"W": r.integers(-1, 2, (8, n_in)).astype(np.int8), "b": r.integers(-50, 50, 8), "M": 20000, "SH": 22, "L": 3},
         {"W": r.integers(-3, 4, (1, 8)).astype(np.int8), "b": r.integers(-5, 5, 1), "M": 0, "SH": 1, "L": None}]
    return QMLP(L, thr=0, meta={"name": f"m{seed}"})

def test_integer_model_matches_hand_calculation(tmp_path):
    m = tiny_model(0); X = np.random.default_rng(1).integers(0, 256, (20, N_IN), dtype=np.uint8)
    ly0, ly1 = m.layers; want = []
    for x in X.astype(int):
        h = [min(3, max(0, ((int(w.astype(int) @ x) + int(b)) * 20000 + (1 << 21)) >> 22)) for w, b in zip(ly0["W"], ly0["b"])]
        want.append(int(ly1["W"][0].astype(int) @ np.array(h)) + int(ly1["b"][0]))
    assert list(m.score(X)) == want
    m.save(tmp_path / "m.npz"); assert list(QMLP.load(tmp_path / "m.npz").score(X)) == want

def test_knobs_keep_records_consistent():
    r = np.random.default_rng(0); R = r.lognormal(2, 1, (200, N_NUM))
    for c in ("spkts", "dpkts", "sbytes", "smean"): R[:, IDX[c]] = np.rint(R[:, IDX[c]]) + 1          # counts are whole numbers
    K = np.exp(r.uniform(np.log(KLO), np.log(KHI), (200, 5)))
    R2 = apply_knobs(R, K)
    changed = {"dur", "sbytes", "spkts", "sinpkt", "sjit", "rate", "sload", "smean", "dload"}
    for name, i in IDX.items():
        if name not in changed: assert np.array_equal(R[:, i], R2[:, i]), name      # everything else untouched
    assert (R2[:, IDX["dur"]] >= R[:, IDX["dur"]]).all() and (R2[:, IDX["sbytes"]] >= np.floor(R[:, IDX["sbytes"]])).all()
    assert np.allclose(apply_knobs(R, np.ones((200, 5)))[:, IDX["rate"]], R[:, IDX["rate"]])
    X = encode(R2, np.zeros((200, N_IN - N_NUM), np.uint8), fit_scaler(R)); assert X.shape == (200, N_IN) and X.dtype == np.uint8

@pytest.fixture
def pack(tmp_path):
    d = tmp_path / "pack"; d.mkdir()
    for s in range(3): tiny_model(s).save(d / f"m{s}.npz")
    np.savez(d / "canary.npz", X=np.random.default_rng(9).integers(0, 256, (16, N_IN), dtype=np.uint8))
    priv, pub = modelpack.keygen(str(tmp_path / "keys")); modelpack.sign(str(d), priv, 1)
    return d, priv, pub, tmp_path

def test_signed_pack_verifies_and_tampering_is_rejected(pack):
    d, priv, pub, tmp = pack
    models, man = modelpack.verify(str(d), pub); assert len(models) == 3 and man["version"] == 1
    tiny_model(7).save(d / "m1.npz")                                   # swap in a different model
    with pytest.raises(ValueError, match="hash"): modelpack.verify(str(d), pub)
    modelpack.build_manifest(str(d), 1)                                # attacker fixes the hashes but cannot sign
    with pytest.raises(ValueError, match="signature"): modelpack.verify(str(d), pub)

def test_install_is_versioned(pack):
    d, priv, pub, tmp = pack; root = tmp / "pool"; root.mkdir()
    modelpack.install(str(d), str(root), pub); assert os.path.realpath(root / "current").endswith("v1")
    with pytest.raises(ValueError, match="not newer"): modelpack.install(str(d), str(root), pub)
    modelpack.sign(str(d), priv, 2); modelpack.install(str(d), str(root), pub)
    assert os.path.realpath(root / "current").endswith("v2") and (root / "v1").exists()      # old pack kept for rollback

@pytest.mark.skipif(shutil.which("g++") is None, reason="needs g++")
def test_generated_hls_code_matches_python(pack, tmp_path):
    d, *_ = pack; out = tmp_path / "hls"
    subprocess.run([sys.executable, str(ROOT / "hw/gen_hls.py"), str(d / "m0.npz"), str(out), "none"], check=True)
    subprocess.run(["g++", "-O1", "-o", "tb", "tb.cpp", "qmlp.cpp"], cwd=out, check=True)
    r = subprocess.run(["./tb"], cwd=out, capture_output=True, text=True); assert "PASS" in r.stdout, r.stdout
