"""Perturbation renderer whose reference is a minibrot NUCLEUS.
The nucleus orbit is exactly periodic (Z_p = 0), so the reference is just p
numbers, reused forever -> no per-frame high-precision work at any depth."""
import numpy as np, mpmath as mp
from numba import njit, prange

BAIL = 1e10

def nucleus_mp(c_guess, p, dps=60):
    mp.mp.dps = dps
    c = mp.mpc(c_guess)
    for _ in range(80):
        z = mp.mpc(0); dz = mp.mpc(0)
        for _ in range(p):
            dz = 2*z*dz + 1; z = z*z + c
        st = z/dz; c -= st
        if abs(st) < mp.mpf(10)**(-dps+5): break
    return c

def reference(c0, p):
    """periodic orbit Z_0..Z_{p-1} (Z_0 = 0) in double, plus complex size s."""
    Z = np.zeros(p, complex); z = mp.mpc(0)
    b = mp.mpc(1); l = mp.mpc(1)
    for n in range(1, p):
        z = z*z + c0
        Z[n] = complex(z)
        l = 2*z*l; b = b + 1/l
    s = complex(1/(b*l*l))
    return Z, s

def render(Zr, Zi, dcx, dcy, width, rot, W, H, maxiter, ss, need=None):
    """(dcx,dcy): view centre relative to the nucleus. Returns nu (-1 inside)
    and distance estimate in pixels. `need` (H x W bool) skips pixels nobody will see."""
    if need is None:
        need = np.ones((H, W), np.bool_)
    return _render(Zr, Zi, dcx, dcy, width, rot, W, H, maxiter, ss, need)


@njit(parallel=True, fastmath=False, cache=True)
def _render(Zr, Zi, dcx, dcy, width, rot, W, H, maxiter, ss, need):
    p = Zr.shape[0]
    nu = np.empty((H, W, ss*ss)); de = np.empty((H, W, ss*ss))
    px = width / W; cr = np.cos(rot); sr = np.sin(rot)
    for j in prange(H):
        for i in range(W):
            if not need[j, i]:
                for k in range(ss*ss):
                    nu[j, i, k] = -1.0; de[j, i, k] = 0.0
                continue
            for k in range(ss*ss):
                ox = (i + (k % ss + 0.5)/ss - W/2) * px
                oy = (j + (k // ss + 0.5)/ss - H/2) * px
                ar = dcx + ox*cr - oy*sr      # Delta c
                ai = dcy + ox*sr + oy*cr
                xr = 0.0; xi = 0.0            # delta z
                dr = 0.0; di = 0.0            # dz/dc
                m = 0; n = 0; r2 = 0.0
                szr = 0.0; szi = 0.0; chk = 16
                esc = False
                while n < maxiter:
                    zr = Zr[m] + xr; zi = Zi[m] + xi       # full z_n
                    ndr = 2*(zr*dr - zi*di) + 1
                    di = 2*(zr*di + zi*dr); dr = ndr
                    # delta' = 2 Z delta + delta^2 + dc
                    t = 2*Zr[m]*xr - 2*Zi[m]*xi + xr*xr - xi*xi + ar
                    xi = 2*Zr[m]*xi + 2*Zi[m]*xr + 2*xr*xi + ai
                    xr = t
                    m += 1; n += 1
                    if m == p: m = 0
                    zr = Zr[m] + xr; zi = Zi[m] + xi
                    r2 = zr*zr + zi*zi
                    if r2 > BAIL:
                        esc = True; break
                    # rebase (Zhuoran): jump back to reference start
                    if r2 < xr*xr + xi*xi:
                        xr = zr; xi = zi; m = 0
                    if abs(zr - szr) + abs(zi - szi) < 1e-13*(abs(szr)+abs(szi)) + 1e-300:
                        break
                    if n == chk:
                        szr = zr; szi = zi; chk *= 2
                if esc:
                    lz = 0.5*np.log(r2)
                    nu[j, i, k] = n + 1 - np.log(lz/np.log(2.0))/np.log(2.0)
                    de[j, i, k] = np.sqrt(r2)*lz/np.sqrt(dr*dr + di*di)/px
                else:
                    nu[j, i, k] = -1.0; de[j, i, k] = 0.0
    return nu, de

MAIN = (np.zeros(1), np.zeros(1))   # nucleus c=0, period 1: plain z^2+c
