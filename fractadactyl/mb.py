"""Tiny double-precision Mandelbrot core for the minibrot-splice PoC."""
import numpy as np
from numba import njit, prange

BAILOUT = 1e10


@njit(parallel=True, fastmath=True, cache=True)
def render(cx, cy, width, rot, W, H, maxiter, ss):
    """Returns (nu, de_px): smooth iteration count (-1 = interior) and
    distance estimate in pixels. ss = supersample grid per axis."""
    nu = np.empty((H, W, ss * ss))
    de = np.empty((H, W, ss * ss))
    px = width / W
    cr, sr = np.cos(rot), np.sin(rot)
    for j in prange(H):
        for i in range(W):
            for k in range(ss * ss):
                ox = (i + (k % ss + 0.5) / ss - W / 2) * px
                oy = (j + (k // ss + 0.5) / ss - H / 2) * px
                c_re = cx + ox * cr - oy * sr
                c_im = cy + ox * sr + oy * cr
                zr = 0.0; zi = 0.0; dr = 0.0; di = 0.0
                n = 0
                r2 = 0.0
                szr = 0.0; szi = 0.0; chk = 8
                while n < maxiter:
                    # dz/dc = 2 z dz + 1
                    ndr = 2 * (zr * dr - zi * di) + 1
                    ndi = 2 * (zr * di + zi * dr)
                    dr = ndr; di = ndi
                    nzr = zr * zr - zi * zi + c_re
                    zi = 2 * zr * zi + c_im
                    zr = nzr
                    n += 1
                    r2 = zr * zr + zi * zi
                    if r2 > BAILOUT:
                        break
                    # Brent-style periodicity check -> early interior exit
                    if abs(zr - szr) + abs(zi - szi) < 1e-14 * (abs(szr) + abs(szi) + 1e-300):
                        n = maxiter
                        r2 = 0.0
                        break
                    if n == chk:
                        szr = zr; szi = zi; chk *= 2
                if r2 > BAILOUT:
                    lz = 0.5 * np.log(r2)
                    nu[j, i, k] = n + 1 - np.log(lz / np.log(2.0)) / np.log(2.0)
                    dmag = np.sqrt(dr * dr + di * di)
                    de[j, i, k] = (np.sqrt(r2) * lz / dmag) / px
                else:
                    nu[j, i, k] = -1.0
                    de[j, i, k] = 0.0
    return nu, de


def ball_period(c, r, maxiter=200000):
    """Smallest n where the disc |c'-c|<r maps over 0 at iterate n
    (Munafo/mathr ball method) -> period of a nearby minibrot."""
    z = 0j; dz = 0j
    for n in range(1, maxiter):
        dz = 2 * z * dz + 1
        z = z * z + c
        if abs(z) < abs(dz) * r:
            return n
        if abs(z) > 4:
            return None
    return None


def nucleus(c, p, steps=64):
    """Newton for z_p(c) = 0."""
    for _ in range(steps):
        z = 0j; dz = 0j
        for _ in range(p):
            dz = 2 * z * dz + 1
            z = z * z + c
        step = z / dz
        c -= step
        if abs(step) < 1e-17 * max(1.0, abs(c)):
            break
    return c


def mini_size(c0, p):
    """Complex size/orientation of minibrot at nucleus c0 (mathr's estimate).
    Mini is approximately  c = c0 + s * C,  C in the main-set plane."""
    b = 1 + 0j; l = 1 + 0j; z = 0j
    for _ in range(1, p):
        z = z * z + c0
        l = 2 * z * l
        b = b + 1 / l
    return 1 / (b * l * l)
