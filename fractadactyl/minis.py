"""Find genuine island minibrots and validate them against the main set."""
import numpy as np, mpmath as mp
from . import pert
from .mb import ball_period

_main_cache = {}
def main_mask(W, H):
    if (W, H) not in _main_cache:
        a, _ = pert.render(*pert.MAIN, -0.75, 0.0, 3.0, 0.0, W, H, 5000, 1)
        _main_cache[(W, H)] = a < 0
    return _main_cache[(W, H)]

def validate(c0, p, s, W=64, H=48):
    Z, _ = pert.reference(c0, p)
    d = s*complex(-0.75, 0)
    b, _ = pert.render(Z.real.copy(), Z.imag.copy(), d.real, d.imag, 3.0*abs(s), np.angle(s), W, H, 5000*p, 1)
    return np.mean((b < 0) == main_mask(W, H)), Z

def find(seed, r, pmax=60000):
    p = ball_period(seed, r, pmax)
    if p is None: return None
    c0 = pert.nucleus_mp(seed, p)
    _, s = pert.reference(c0, p)
    score, Z = validate(c0, p, s)
    return dict(p=p, c0=c0, s=s, score=score, Z=Z, dist=abs(complex(c0) - seed)/abs(s))

if __name__ == "__main__":
    seed = complex(-0.743643887037151, 0.131825904205330)
    for e in range(3, 13):
        m = find(seed, 10.0**-e)
        if m: print(f"r=1e-{e:<2} p={m['p']:<6} |s|={abs(m['s']):.2e} arg={np.angle(m['s']):+.2f} match={m['score']*100:5.1f}%  dist={m['dist']:.3g}|s|", flush=True)
