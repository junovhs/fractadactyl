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


@njit(fastmath=False, cache=True)
def _attracting(Zr, Zi, m0, x0r, x0i, ar, ai, P):
    """Newton for a period-P point of z -> z^2 + c from the orbit point (phase m0, delta x0).
    True iff it converges to a cycle whose multiplier |dz_P/dz_0| < 1: an attracting cycle
    exists only for c in the interior, so the pixel is inside. Converges in a few steps
    even where the orbit itself would take thousands of periods to settle."""
    p = Zr.shape[0]
    first = 0.0; prev = 0.0
    for it in range(12):
        m = m0; xr = x0r; xi = x0i
        Dr = 1.0; Di = 0.0
        for n in range(P):
            zr = Zr[m] + xr; zi = Zi[m] + xi
            t = 2*(zr*Dr - zi*Di); Di = 2*(zr*Di + zi*Dr); Dr = t
            t = 2*Zr[m]*xr - 2*Zi[m]*xi + xr*xr - xi*xi + ar
            xi = 2*Zr[m]*xi + 2*Zi[m]*xr + 2*xr*xi + ai
            xr = t
            m += 1
            if m == p: m = 0
            zr = Zr[m] + xr; zi = Zi[m] + xi
            if zr*zr + zi*zi > 4.0:
                return False                 # left the disc: not a cycle point
            if zr*zr + zi*zi < xr*xr + xi*xi:
                xr = zr; xi = zi; m = 0
        rr = (Zr[m] + xr) - (Zr[m0] + x0r); ri = (Zi[m] + xi) - (Zi[m0] + x0i)   # f^P(z) - z
        er = Dr - 1.0; ei = Di
        den = er*er + ei*ei
        if den == 0.0 or not np.isfinite(den):
            return False
        sr = (rr*er + ri*ei) / den; si = (ri*er - rr*ei) / den              # step = r / (D - 1)
        x0r -= sr; x0i -= si
        st = abs(sr) + abs(si)
        if it == 0:
            first = st
        elif st <= 1e-7 * first or st < 1e-300:
            return Dr*Dr + Di*Di < 1.0
        elif it >= 2 and st > 0.5 * prev:
            return False                     # not converging quadratically: wrong period
        prev = st
    return False


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
                newton_at = 64                # next n at which a near-return may try Newton
                tries = 0
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
                    dz = abs(zr - szr) + abs(zi - szi); sz = abs(szr) + abs(szi)
                    if dz < 1e-13*sz + 1e-300:
                        break
                    # near-return to the saved point: candidate period n - chk/2; confirm by Newton
                    if tries < 4 and n >= newton_at and dz < 1e-3*sz:
                        if _attracting(Zr, Zi, m, xr, xi, ar, ai, n - chk // 2):
                            break
                        tries += 1; newton_at = 4 * n
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
