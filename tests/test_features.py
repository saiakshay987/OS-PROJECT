import csv, pathlib, sys
import numpy as np, soundfile as sf
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "common"))
from features import SR, NFR, NMEL, log_mel, mel_energies, windows, Vad, MEL_FB

def test_shapes():
    x = (np.random.default_rng(0).normal(0, 300, SR)).astype(np.int16)
    assert log_mel(x).shape == (NFR, NMEL) and log_mel(x).dtype == np.float32
    assert MEL_FB.shape == (NMEL, 257) and (MEL_FB.sum(1) > 0).all()

def test_vad_matches_expected_gate():
    x, sr = sf.read(ROOT / "common/test_wavs/vad_test.wav", dtype="int16")
    assert sr == SR
    rows = list(csv.DictReader(open(ROOT / "common/test_wavs/vad_expected.csv")))
    v, got = Vad(), []
    for w in windows(x):
        r = v.update(mel_energies(w)); got.append((int(r["speech"]), r["n_speech"]))
    assert len(got) == len(rows)
    assert [g for g, _ in got] == [int(r["gate"]) for r in rows]
    assert [n for _, n in got] == [int(r["n_speech"]) for r in rows]

def test_silence_keeps_gate_closed():
    x = (np.random.default_rng(1).normal(0, 40, 20 * SR)).astype(np.int16)
    v = Vad(); assert not any(v.update(mel_energies(w))["speech"] for w in windows(x))
