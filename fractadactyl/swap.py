"""PoC 2: hide a teleport (deep minibrot A -> shallow twin B) while it is tiny.
Everything is rendered in the minis' shared LOCAL coordinates C, where
world X maps C -> c = c_X + s_X * C. The camera lives in local coords, so both
worlds line up automatically (rotation included)."""
import numpy as np, mpmath as mp
from . import pert, minis

SEED = complex(-0.743643887037151, 0.131825904205330)
PATCH_C = complex(-0.75, 0.0)   # patch centre (mini's middle), local coords
PATCH_R = 4.0                   # patch radius, local units (mini is ~2.5 wide)

def load_worlds():
    A = minis.find(SEED, 1e-3)   # p=35, |s|~1.4e-10  (deep, "real")
    B = minis.find(SEED, 1e-4)   # p=39, |s|~2.2e-6   (shallow twin)
    for n, X in (("A", A), ("B", B)):
        print(f"world {n}: p={X['p']} |s|={abs(X['s']):.2e} validation={X['score']*100:.1f}%")
    return A, B

def render_world(X, cen, w, W, H, ss, maxmul=50000):
    d = X['s'] * cen
    Z = X['Z']
    return pert.render(Z.real.copy(), Z.imag.copy(), d.real, d.imag,
                       w*abs(X['s']), np.angle(X['s']), W, H, maxmul*X['p'], ss)

def patch_mask(cen, w, W, H, feather_px=3.0):
    """1 inside patch, 0 outside, soft edge of a few pixels. Local coords."""
    px = w / W
    x = (np.arange(W) + 0.5 - W/2) * px
    y = (np.arange(H) + 0.5 - H/2) * px
    C = cen + x[None, :] + 1j*y[:, None]
    dist = np.abs(C - PATCH_C)
    return np.clip((PATCH_R - dist) / (feather_px*px) + 0.5, 0, 1)

def fit_nu_map(nuA, nuB, mask):
    """Appearance-only colour continuity: log(nuA) ~ a*log(nuB) + b via quantiles."""
    m = (mask > 0.5) & (nuA > 0) & (nuB > 0)
    qs = np.linspace(2, 98, 49)
    la = np.percentile(np.log(nuA[m]), qs); lb = np.percentile(np.log(nuB[m]), qs)
    a, b = np.polyfit(lb, la, 1)
    return a, b

def apply_nu_map(nu, ab):
    a, b = ab
    out = nu.copy(); pos = nu > 0
    out[pos] = np.exp(a*np.log(nu[pos]) + b)
    return out
