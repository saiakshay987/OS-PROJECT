# common/modelpack.py — a 'model pack' is a folder: m0.npz ... mK.npz + canary.npz + manifest.json + manifest.sig
# The manifest lists every file's SHA-256 and the answers each model must give on the canary records.
# The signature covers the manifest. The appliance loads nothing that fails any of these checks.
#   python common/modelpack.py keygen keys/            -> pool_priv.pem (keep OFF the appliance), pool_pub.pem
#   python common/modelpack.py sign   models/pool keys/pool_priv.pem
#   python common/modelpack.py verify models/pool keys/pool_pub.pem
#   python common/modelpack.py install new_pack/ /data/pool keys/pool_pub.pem     (atomic switch, keeps the old pack)
import json, os, shutil, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qmlp import QMLP, sha256_file

def _ssl(*args):
    return subprocess.run(["openssl", *args], capture_output=True, text=True)

def keygen(d):
    os.makedirs(d, exist_ok=True)
    priv, pub = os.path.join(d, "pool_priv.pem"), os.path.join(d, "pool_pub.pem")
    r = _ssl("ecparam", "-name", "prime256v1", "-genkey", "-noout", "-out", priv); assert r.returncode == 0, r.stderr
    r = _ssl("ec", "-in", priv, "-pubout", "-out", pub); assert r.returncode == 0, r.stderr
    os.chmod(priv, 0o600)
    return priv, pub

def build_manifest(d, version=None):
    names = sorted(f for f in os.listdir(d) if f.startswith("m") and f.endswith(".npz"))
    can = np.load(os.path.join(d, "canary.npz"))["X"]
    members = []
    for n in names:
        m = QMLP.load(os.path.join(d, n))
        members.append({"file": n, "sha256": sha256_file(os.path.join(d, n)), "meta": m.meta,
                        "canary": "".join("1" if v else "0" for v in m.predict(can))})
    man = {"version": version or int(time.time()), "members": members,
           "canary_sha256": sha256_file(os.path.join(d, "canary.npz"))}
    json.dump(man, open(os.path.join(d, "manifest.json"), "w"), indent=1)
    return man

def sign(d, priv, version=None):
    build_manifest(d, version)
    r = _ssl("dgst", "-sha256", "-sign", priv, "-out", os.path.join(d, "manifest.sig"), os.path.join(d, "manifest.json"))
    assert r.returncode == 0, r.stderr

def verify(d, pub):
    """Returns (list of QMLP, manifest). Raises ValueError with the reason if anything is wrong."""
    man_p, sig_p = os.path.join(d, "manifest.json"), os.path.join(d, "manifest.sig")
    if not (os.path.exists(man_p) and os.path.exists(sig_p)):
        raise ValueError("manifest or signature missing")
    r = _ssl("dgst", "-sha256", "-verify", pub, "-signature", sig_p, man_p)
    if r.returncode != 0 or "Verified OK" not in r.stdout:
        raise ValueError("signature check failed")
    man = json.load(open(man_p))
    if sha256_file(os.path.join(d, "canary.npz")) != man["canary_sha256"]:
        raise ValueError("canary file changed")
    can = np.load(os.path.join(d, "canary.npz"))["X"]
    models = []
    for e in man["members"]:
        p = os.path.join(d, os.path.basename(e["file"]))
        if not os.path.exists(p) or sha256_file(p) != e["sha256"]:
            raise ValueError(f"{e['file']}: hash mismatch")
        m = QMLP.load(p)
        if "".join("1" if v else "0" for v in m.predict(can)) != e["canary"]:
            raise ValueError(f"{e['file']}: canary self-test failed")
        m.meta["file"] = e["file"]; models.append(m)
    if not models:
        raise ValueError("empty pack")
    return models, man

def install(src, dst_root, pub):
    """Verify src, copy to dst_root/v<version>, then atomically repoint dst_root/current. Old versions stay for rollback."""
    _, man = verify(src, pub)
    cur = os.path.join(dst_root, "current")
    if os.path.islink(cur):
        try:
            old = json.load(open(os.path.join(cur, "manifest.json")))["version"]
            if man["version"] <= old: raise ValueError(f"version {man['version']} is not newer than installed {old}")
        except FileNotFoundError: pass
    dst = os.path.join(dst_root, f"v{man['version']}")
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst)
    verify(dst, pub)                                   # check the copy too
    tmp = cur + ".new"
    if os.path.lexists(tmp): os.remove(tmp)
    os.symlink(os.path.basename(dst), tmp); os.replace(tmp, cur)
    return dst

if __name__ == "__main__":
    cmd, a = sys.argv[1], sys.argv[2:]
    try:
        if cmd == "keygen": print(*keygen(a[0]))
        elif cmd == "sign": sign(a[0], a[1], int(a[2]) if len(a) > 2 else None); print("signed", a[0])
        elif cmd == "verify": ms, man = verify(a[0], a[1]); print(f"OK: version {man['version']}, {len(ms)} models")
        elif cmd == "install": print("installed", install(a[0], a[1], a[2]))
        else: sys.exit("unknown command")
    except (ValueError, AssertionError) as e:
        sys.exit(f"REJECTED: {e}")
