"""Persistent twin library (LIB-01).

`build` collects validated island minibrots once and stores, per twin, everything a swap
needs without high-precision work: nucleus (as a decimal string), period, complex size,
the periodic reference orbit Z_0..Z_{p-1}, and a cheap lace signature. `pick` ranks the
library against a target by signature distance, then runs the full composite mismatch
score (twins.mismatch) only on the top K.

    python -m fractadactyl.library build [--budget 600] [--seed-from data/poc2_twins.pkl]
    python -m fractadactyl.library pick --period 35 --seed="-0.7436438870371587+0.1318259042053120j"
"""
import argparse, pickle, time
import numpy as np
from . import pert, minis, twins
from .swap import PATCH_C, render_world

LIB_PATH = "data/twins.npz"
SIG_WIDTHS = (40.0, 16.0, 9.0)     # same framings twins.mismatch scores
SIG_W, SIG_H = 24, 14          # 16x9 already ranks the true best #1 of 1934 (PoC-2 target)


def signature(X):
    """Colour-map-free lace fingerprint: per framing, rank-normalised log iteration count
    (interior = -1) and distance-estimate shading, at low resolution."""
    parts = []
    for w in SIG_WIDTHS:
        nu, de = render_world(X, PATCH_C, w, SIG_W, SIG_H, 1, maxmul=3000)
        nu = nu[..., 0]; de = de[..., 0]
        rank = np.full(nu.shape, -1.0)
        ext = nu > 0
        if ext.any():
            order = np.argsort(np.argsort(np.log(nu[ext])))
            rank[ext] = order / max(1, ext.sum() - 1)
        parts += [rank.ravel(), np.tanh(de * 0.6).ravel()]
    return np.concatenate(parts).astype(np.float32)


def _parse_c(s):
    return complex(s.replace(" ", "").strip("()"))


def _twin_from(c0, p):
    Z, s = pert.reference(c0, p)
    return dict(p=p, s=s, Z=Z, c0=str(c0))


def build(budget_s=600, seed_from=None, out=LIB_PATH, seed=None):
    found = []
    if seed_from:                                   # reuse an earlier validated search
        for _, info, _ in pickle.load(open(seed_from, "rb")):
            c0 = pert.nucleus_mp(_parse_c(info["c0"]), info["p"])
            found.append(_twin_from(c0, info["p"]) | dict(valid=info["score"]))
        print(f"imported {len(found)} validated minis from {seed_from}", flush=True)
    if budget_s > 0:
        for m in twins.candidates(budget_s, seed=seed if seed is not None else int(time.time())):
            found.append(dict(p=m["p"], s=m["s"], Z=m["Z"], c0=str(m["c0"]), valid=m["score"]))
    uniq = {}
    for t in found:                                 # dedupe by period + nucleus
        c = _parse_c(t["c0"])
        uniq.setdefault((t["p"], round(c.real, 12), round(c.imag, 12)), t)
    lib = list(uniq.values())
    t0 = time.time()
    sigs = np.stack([signature(t) for t in lib])
    print(f"signatures for {len(lib)} twins in {time.time()-t0:.0f}s", flush=True)
    offs = np.cumsum([0] + [t["p"] for t in lib])
    np.savez_compressed(out,
        p=np.array([t["p"] for t in lib]), s=np.array([t["s"] for t in lib]),
        c0=np.array([t["c0"] for t in lib]), valid=np.array([t["valid"] for t in lib]),
        Z=np.concatenate([t["Z"] for t in lib]), Z_off=offs, sig=sigs.astype(np.float16))
    print(f"wrote {out}: {len(lib)} validated minis", flush=True)
    return len(lib)


def load(path=LIB_PATH):
    with np.load(path) as f:
        d = {k: f[k] for k in f.files}     # npz members decompress on every access; read once
    off = d["Z_off"]
    return [dict(p=int(d["p"][i]), s=complex(d["s"][i]), c0=str(d["c0"][i]), valid=float(d["valid"][i]),
                 Z=d["Z"][off[i]:off[i + 1]], sig=d["sig"][i].astype(np.float32)) for i in range(len(d["p"]))]


def pick(target, lib, k=16):
    """Best twin for `target` (dict with p, s, Z): signature shortlist, then full score."""
    tsig = signature(target)
    tc = _parse_c(target["c0"]) if "c0" in target else None
    def is_self(t):
        return tc is not None and t["p"] == target["p"] and abs(_parse_c(t["c0"]) - tc) < abs(target["s"]) * 1e-3
    pool = [t for t in lib if not is_self(t)]
    dist = np.array([np.mean((t["sig"] - tsig) ** 2) for t in pool])
    short = [pool[i] for i in np.argsort(dist)[:k]]
    scored = sorted(((twins.mismatch(target, t)[0], i, t) for i, t in enumerate(short)), key=lambda x: x[:2])
    err, _, best = scored[0]
    _, ab = twins.mismatch(target, best)
    return best, err, ab


def main():
    ap = argparse.ArgumentParser(prog="python -m fractadactyl.library")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--budget", type=float, default=600)
    b.add_argument("--seed-from"); b.add_argument("--out", default=LIB_PATH)
    b.add_argument("--rng-seed", type=int, help="search RNG seed (default: time-based, so reruns find new minis)")
    q = sub.add_parser("pick"); q.add_argument("--period", type=int, required=True)
    q.add_argument("--seed", required=True); q.add_argument("--k", type=int, default=16)
    q.add_argument("--lib", default=LIB_PATH)
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.budget, a.seed_from, a.out, a.rng_seed)
        return
    t0 = time.time()
    lib = load(a.lib)
    c0 = pert.nucleus_mp(_parse_c(a.seed), a.period)
    target = _twin_from(c0, a.period)
    score, _ = minis.validate(c0, a.period, target["s"])
    best, err, ab = pick(target, lib, a.k)
    print(f"target p={a.period} |s|={abs(target['s']):.2e} (valid {score*100:.1f}%)  library {len(lib)} twins")
    print(f"best twin p={best['p']} |s|={abs(best['s']):.2e} c0={best['c0']}")
    print(f"mismatch {err:.2f}%  colour map a={ab[0]:.3f} b={ab[1]:.3f}  in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
