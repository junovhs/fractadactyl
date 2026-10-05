"""Chained hidden swaps (POC-02, DEC-02).

A *world* is a minibrot X (nucleus c0, period p, complex size s, periodic reference Z).
Its local coordinates C map to c = c0 + s*C, so every world looks like the main set at C.
The camera (centre, width, rotation theta) lives in the current world's local coords.

Each segment dives toward a sub-minibrot M found ahead of the camera inside X. When M's
patch is <= SWAP_PX pixels wide, a library twin B (a shallow look-alike of M) fades in
over the patch (DEC-02); once the patch covers the screen the camera is re-expressed in
B's local coords and B becomes the current world. True depth therefore never accumulates.
With use_twins=False the "twin" is M itself: the real, ever-deeper control path.
"""
import re, time
import numpy as np, mpmath as mp
from . import pert, minis, library
from .color import colorize

PATCH_C, PATCH_R = -0.75 + 0j, 4.0     # patch around a mini, in its own local coords
INNER = 0.6                            # inner 60% of the patch is solid
MAIN = dict(p=1, s=1 + 0j, Z=np.zeros(1, complex), c0=mp.mpc(0))
_BASE_POINTS = [complex(-0.7436438870371587, 0.1318259042053120),  # seahorse valley (p=39 mini)
                complex(-1.2537, 0.0384),                            # west tendril (p=41)
                complex(-0.10109636384562, 0.95628651080914),        # upper antenna (p=13)
                complex(0.4245, 0.2075),                             # east rim (p=16)
                complex(-0.7746806106269039, 0.1374168856037867)]    # seahorse, second (p=24)
DIVE_POINTS = _BASE_POINTS + [p.conjugate() for p in _BASE_POINTS]  # mirror images work too


def mpc_from_str(s):
    s = s.replace(" ", "").strip("()").rstrip("j")
    m = re.match(r"^([+-]?[^+-]+(?:[eE][+-]?\d+)?)([+-].+)$", s)
    return mp.mpc(mp.mpf(m.group(1)), mp.mpf(m.group(2)))


def world_dps(s):
    return max(40, int(-np.log10(abs(s))) + 30)


def mp_ball_period(c, r, pmax):
    """Lowest n where the disc |c'-c| < r maps over 0 (Munafo/mathr), in mp precision."""
    z = mp.mpc(0); dz = mp.mpc(0)
    for n in range(1, pmax):
        dz = 2 * z * dz + 1; z = z * z + c
        az = abs(z)
        if az < abs(dz) * r: return n
        if az > 4: return None
    return None


# DEC-03: every candidate mini is validated against the main set (ball-period also finds satellites)
def find_sub_mini(X, P, sigma_range=(1e-6, 1e-3), pmax=400000):
    """A validated island minibrot near X-local point P, with relative size in range."""
    dps = world_dps(abs(X["s"]) * sigma_range[0])
    mp.mp.dps = dps
    cX = X["c0"]; sX = mp.mpc(X["s"])
    cP = cX + sX * mp.mpc(P)
    for j in range(2, 10):
        mp.mp.dps = dps
        r = abs(X["s"]) * 10.0 ** -j
        p = mp_ball_period(cP, mp.mpf(r), pmax)
        if not p or p <= X["p"]: continue
        try:
            c0 = pert.nucleus_mp(cP, p, dps)
            Z, s = pert.reference(c0, p)
        except ZeroDivisionError:          # Newton landed on a lower-period nucleus
            continue
        sigma = s / X["s"]
        if not (sigma_range[0] <= abs(sigma) <= sigma_range[1]): continue
        CM = complex((c0 - cX) / sX)
        if abs(CM - P) > 0.5: continue
        score, _ = minis.validate(c0, p, s)
        if score < 0.97: continue
        return dict(p=p, c0=c0, s=s, Z=Z, sigma=sigma, CM=CM, valid=score)
    return None


def _find_with_fallback(X, rng):
    """Try dive points in random order until one has a usable sub-mini."""
    for i in rng.permutation(len(DIVE_POINTS)):
        M = find_sub_mini(X, DIVE_POINTS[i])
        if M is not None:
            return DIVE_POINTS[i], M
    return None, None


def plan(n_swaps, lib=None, seed=0, log=print, budget_s=None):
    """Segments: world X, its sub-mini M, the twin B that replaces M, colour map B->M,
    and the dive target Q (X-local) = where the next segment's dive point sits inside M."""
    rng = np.random.default_rng(seed)
    X = MAIN; segs = []; t0 = time.time()
    P, M = _find_with_fallback(X, rng)
    for k in range(n_swaps):
        if M is None or (budget_s and time.time() - t0 > budget_s):
            log(f"  chain stops at {k} swaps"); break
        if lib is not None:
            B, err, ab = library.pick(dict(M, c0=str(M["c0"])), lib)
            B = dict(B, c0=pert.nucleus_mp(mpc_from_str(B["c0"]), B["p"], world_dps(B["s"])))
        else:
            B, err, ab = M, 0.0, (1.0, 0.0)
        P_next, M_next = _find_with_fallback(B, rng) if k + 1 < n_swaps else (DIVE_POINTS[0], None)
        P_next = P_next if P_next is not None else DIVE_POINTS[0]
        Q = M["CM"] + M["sigma"] * P_next
        log(f"  seg {k}: world p={X['p']} |s|={abs(X['s']):.1e} -> mini p={M['p']} |sigma|={abs(M['sigma']):.1e}"
            f"  twin p={B['p']} |s|={abs(B['s']):.1e} mismatch {err:.2f}%  ({time.time()-t0:.0f}s)")
        segs.append(dict(X=X, M=M, B=B, ab=ab, err=err, Q=Q))
        X, M = B, M_next
    segs.append(dict(X=X, M=None, B=None, ab=None, err=None, Q=P_next if segs else P))
    return segs


def render_world(X, center, w, theta, W, H, ss, maxmul, need=None):
    d = X["s"] * center
    return pert.render(X["Z"].real.copy(), X["Z"].imag.copy(), d.real, d.imag,
                       w * abs(X["s"]), np.angle(X["s"]) + theta, W, H, maxmul * X["p"], ss, need)


def patch_weight(center, w, theta, W, H):
    """Soft patch mask for a camera expressed in the incoming mini's local coords."""
    x = (np.arange(W) + 0.5 - W / 2) * (w / W)
    y = (np.arange(H) + 0.5 - H / 2) * (w / W)
    C = center + (x[None, :] + 1j * y[:, None]) * np.exp(1j * theta)
    r = np.abs(C - PATCH_C) / PATCH_R
    t = np.clip((1 - r) / (1 - INNER), 0, 1)
    return t * t * (3 - 2 * t)


def shade(nu, de, ab):
    out = nu.copy(); pos = nu > 0
    out[pos] = np.exp(ab[0] * np.log(nu[pos]) + ab[1])
    return colorize(out, de, freq=1.5)


# DEC-02: swap while the patch is ~swap_px render pixels, smoothstep fade, feathered patch, matched twin.
# DEC-01: these thresholds are only accepted because they survive blind A/B viewing.
def run(segs, out_frame, W=640, H=360, ss=2, fps=30, dec_per_s=0.6, swap_px=6.0, fade=10,
        tail_s=3.0, maxmul=5000, budget_s=None, log=print):
    """Render the chain. out_frame(k, rgb) stores a frame. Returns per-frame records."""
    rate = 10 ** (-dec_per_s / fps)
    center, w, theta = complex(-0.6, 0), 3.5, 0.0
    cmap = (1.0, 0.0)                      # current world's nu -> display nu (log-linear)
    recs = []; k = 0; t_start = time.time()
    for si, seg in enumerate(segs):
        X, M, Q = seg["X"], seg["M"], seg["Q"]
        swap_f = None; tail_frames = int(tail_s * fps)
        while True:
            if budget_s and time.time() - t_start > budget_s:
                log(f"  render budget hit at frame {k}"); return recs, False
            t0 = time.time()
            done_seg = False
            m = None
            if M is not None:
                sig = M["sigma"]
                if swap_f is None and 2 * PATCH_R * abs(sig) / w * W >= swap_px:   # patch has grown to swap size
                    swap_f = 0
                if swap_f is not None:
                    cB, wB, thB = (center - M["CM"]) / sig, w / abs(sig), theta - np.angle(sig)
                    a = min(1.0, (swap_f + 1) / fade); a = a * a * (3 - 2 * a)
                    m = patch_weight(cB, wB, thB, W, H) * a
            # only render each world where it is visible: X outside the solid patch, B inside it
            nuX, deX = render_world(X, center, w, theta, W, H, ss, maxmul, None if m is None else m < 1.0)
            rgb = shade(nuX, deX, cmap)
            if m is not None:
                cmapB = (cmap[0] * seg["ab"][0], cmap[0] * seg["ab"][1] + cmap[1])
                nuB, deB = render_world(seg["B"], cB, wB, thB, W, H, ss, maxmul, m > 0.0)
                rgbB = shade(nuB, deB, cmapB)
                mm = m[..., None]
                rgb = (rgb * (1 - mm) + rgbB * mm).astype(np.uint8)
                swap_f += 1
                if a >= 1.0 and m.min() >= 1.0:          # patch covers the screen
                    center, w, theta, cmap = cB, wB, thB, cmapB
                    done_seg = True
            elif M is None:
                tail_frames -= 1
                done_seg = tail_frames <= 0
            out_frame(k, rgb)
            recs.append(dict(frame=k, seg=si, secs=time.time() - t0,
                             swapping=swap_f is not None and not done_seg, swap_start=swap_f == 1))
            if k % 30 == 0:
                log(f"  frame {k} seg {si} width {w:.2e} {recs[-1]['secs']:.2f}s/frame")
            k += 1
            # advance the camera toward this segment's dive target (or re-expressed one)
            tgt = Q if not done_seg else None
            w *= rate
            if tgt is not None: center = tgt + (center - tgt) * rate
            if done_seg: break
    return recs, True
