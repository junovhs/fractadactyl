"""Gather validated island minibrots and score each as a stand-in for A."""
import numpy as np, time, random, pickle
from . import pert, minis
from .swap import SEED, PATCH_C, PATCH_R, render_world, fit_nu_map, apply_nu_map
from .color import colorize
from .mb import ball_period

def soft_mask(cen, w, W, H, inner=0.6):
    px = w / W
    x = (np.arange(W) + 0.5 - W/2) * px; y = (np.arange(H) + 0.5 - H/2) * px
    r = np.abs(cen + x[None, :] + 1j*y[:, None] - PATCH_C) / PATCH_R
    t = np.clip((1 - r) / (1 - inner), 0, 1)
    return t*t*(3 - 2*t)                       # smoothstep feather, inner 60% solid

def candidates(budget_s=600, pmax=2500):
    rng = random.Random(1); out = {}; t0 = time.time()
    while time.time() - t0 < budget_s:
        rad = 10 ** rng.uniform(-5.5, -1.5)
        ang = rng.uniform(0, 2*np.pi)
        seed = SEED + rad*np.exp(1j*ang) if rng.random() < 0.7 else \
               complex(rng.uniform(-1.8, 0.45), rng.uniform(0, 1.1))
        r = rad / 10 ** rng.uniform(0.5, 2)
        p = ball_period(seed, r, pmax)
        if p is None or p < 8 or p > pmax: continue
        try:
            c0 = pert.nucleus_mp(seed, p, dps=40)
            Z, s = pert.reference(c0, p)
        except (ZeroDivisionError, ValueError, OverflowError):
            continue
        if not (1e-9 < abs(s) < 1e-2): continue
        key = (p, round(float(c0.real), 12), round(float(c0.imag), 12))
        if key in out: continue
        score, _ = minis.validate(c0, p, s)
        if score < 0.97: continue
        out[key] = dict(p=p, c0=c0, s=s, Z=Z, score=score)
        print(f"  found p={p:<5} |s|={abs(s):.1e} valid={score*100:.1f}%  ({len(out)} so far)", flush=True)
    return list(out.values())

def mismatch(A, B):
    """How visible is A->B at swap-ish scales? Composite vs real, a few framings."""
    fits = []
    W, H = 192, 108
    for w in (40.0, 16.0, 9.0):      # patch ~20%, 50%, ~90% of width
        nA, dA = render_world(A, PATCH_C, w, W, H, 2, maxmul=3000)
        nB, dB = render_world(B, PATCH_C, w, W, H, 2, maxmul=3000)
        fits.append((nA, dA, nB, dB, soft_mask(PATCH_C, w, W, H)))
    # one colour map fitted on all framings together
    nA = np.concatenate([f[0].mean(2).ravel() for f in fits]); nB = np.concatenate([f[2].mean(2).ravel() for f in fits])
    mk = np.concatenate([f[4].ravel() for f in fits])
    ab = fit_nu_map(nA, nB, mk)
    total = 0.0
    for fa, dA, fb, dB, m in fits:
        real = colorize(fa, dA, freq=1.5).astype(float)
        fake = colorize(apply_nu_map(fb, ab), dB, freq=1.5).astype(float)
        comp = real*(1-m[..., None]) + fake*m[..., None]
        total += np.abs(comp - real).mean()/2.55
    return total/3, ab

if __name__ == "__main__":
    A = minis.find(SEED, 1e-3)
    print(f"A: p={A['p']} |s|={abs(A['s']):.2e}")
    B0 = minis.find(SEED, 1e-4)
    cands = [B0] + candidates()
    scored = []
    for B in cands:
        e, ab = mismatch(A, B)
        scored.append((e, B, ab))
        print(f"score p={B['p']:<5} |s|={abs(B['s']):.1e}  mismatch {e:5.2f}%", flush=True)
    scored.sort(key=lambda t: t[0])
    print("BEST:", scored[0][1]['p'], f"{scored[0][0]:.2f}%   (old twin p=39 was {[x[0] for x in scored if x[1] is B0][0]:.2f}%)")
    pickle.dump([(e, dict(p=B['p'], c0=str(B['c0']), s=B['s'], score=B['score']), ab) for e, B, ab in scored], open("data/poc2_twins.pkl", "wb"))
