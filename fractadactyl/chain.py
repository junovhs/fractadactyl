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


def plan(n_swaps, lib=None, seed=0, log=print, budget_s=None, max_twin_p=64):
    """Segments: world X, its sub-mini M, the twin B that replaces M, colour map B->M,
    and the dive target Q (X-local) = where the next segment's dive point sits inside M.
    Per-frame cost is proportional to the current world's period, so twins are limited to
    period <= max_twin_p: that bounds the cost of every frame, however long the chain."""
    if lib is not None and max_twin_p:
        lib = [t for t in lib if t["p"] <= max_twin_p]
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
    # aim the whole chain at one nested point: segment k's target is segment k+1's target
    # seen through M_k (B-local ~ M-local), so the zoom's fixed point never jumps at a handoff
    for k in range(len(segs) - 2, -1, -1):
        M = segs[k]["M"]
        segs[k]["Q"] = M["CM"] + M["sigma"] * segs[k + 1]["Q"]
    return segs


def render_world(X, center, w, theta, W, H, ss, maxmul, need=None):
    d = X["s"] * center
    return pert.render(X["Z"].real.copy(), X["Z"].imag.copy(), d.real, d.imag,
                       w * abs(X["s"]), np.angle(X["s"]) + theta, W, H, maxmul * X["p"], ss, need)


SEAM_R = (1.5, 3.9)                    # seam may wander between these radii (mini-local units)
SEAM_N = 512                           # seam-cost render size (pixels across the patch)


def _hue(nu, ab, freq=1.5):
    """Display hue phase (colorize's t) after the log-linear colour map; NaN inside."""
    t = np.full(nu.shape, np.nan); pos = nu > 0
    t[pos] = (ab[0] * np.log(nu[pos]) + ab[1]) * freq
    return t


def seam(seg, cmap, maxmul, n_ang=720, n_rad=96, bend=0.05, log=print):
    """Optimal seam (panorama-stitching style): a closed curve r(phi) around the incoming
    mini, in its local polar coords, along which the outgoing world X and the twin B look
    most alike. Computed once per swap, so it is fixed in world space and zooms with it."""
    t0 = time.time()
    X, M, B = seg["X"], seg["M"], seg["B"]
    sig, N, R = M["sigma"], SEAM_N, SEAM_R[1]
    cmapB = (cmap[0] * seg["ab"][0], cmap[0] * seg["ab"][1] + cmap[1])
    nuX, _ = render_world(X, M["CM"] + sig * PATCH_C, 2 * R * abs(sig), np.angle(sig), N, N, 1, maxmul)
    nuB, _ = render_world(B, PATCH_C, 2 * R, 0.0, N, N, 1, maxmul)
    tX, tB = _hue(nuX[..., 0], cmap), _hue(nuB[..., 0], cmapB)
    diff = 1 - np.cos(2 * np.pi * (tX - tB))                     # 0..2, cyclic hue distance
    diff[np.isnan(tX) != np.isnan(tB)] = 4.0                     # inside vs outside: worst
    diff[np.isnan(tX) & np.isnan(tB)] = 0.0
    # sample on a polar grid (nearest pixel)
    phi = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    rad = np.linspace(SEAM_R[0], R * 0.98, n_rad)
    P = rad[None, :] * np.exp(1j * phi[:, None])                 # offsets from PATCH_C
    ix = np.clip(((P.real + R) / (2 * R) * N).astype(int), 0, N - 1)
    iy = np.clip(((P.imag + R) / (2 * R) * N).astype(int), 0, N - 1)
    cost = diff[iy, ix]                                          # (n_ang, n_rad)
    # closed-loop DP: radius index moves by <= 1 per angle step (each move costs `bend`, so
    # the seam stays smooth); try every other start radius
    best = (np.inf, None)
    for r0 in range(0, n_rad, 2):
        acc = np.full(n_rad, np.inf); acc[r0] = cost[0, r0]
        back = np.zeros((n_ang, n_rad), np.int8)
        for a in range(1, n_ang):
            cand = np.stack([np.r_[np.inf, acc[:-1]] + bend, acc, np.r_[acc[1:], np.inf] + bend])  # from r-1, r, r+1
            j = cand.argmin(0); back[a] = j - 1
            acc = cand[j, np.arange(n_rad)] + cost[a]
        ends = [r for r in (r0 - 1, r0, r0 + 1) if 0 <= r < n_rad]
        e = min(ends, key=lambda r: acc[r])
        if acc[e] < best[0]:
            path = np.empty(n_ang, int); path[-1] = e
            for a in range(n_ang - 1, 0, -1):
                path[a - 1] = path[a] + back[a, path[a]]
            best = (acc[e], path)
    r_phi = rad[best[1]]
    log(f"  seam: mean cost {best[0] / n_ang:.3f} (straight circle {cost.mean(0).min():.3f}),"
        f" r {r_phi.min():.2f}..{r_phi.max():.2f}  ({time.time() - t0:.1f}s)")
    return phi, r_phi


def patch_weight(center, w, theta, W, H, seam_pr, feather_px=2.5):
    """Patch mask for a camera in the incoming mini's local coords: 1 inside the seam,
    0 outside, with a feather of a few *screen* pixels."""
    x = (np.arange(W) + 0.5 - W / 2) * (w / W)
    y = (np.arange(H) + 0.5 - H / 2) * (w / W)
    D = center - PATCH_C + (x[None, :] + 1j * y[:, None]) * np.exp(1j * theta)
    phi, r_phi = seam_pr
    rs = np.interp(np.angle(D) % (2 * np.pi), np.r_[phi, 2 * np.pi], np.r_[r_phi, r_phi[0]])
    return np.clip((rs - np.abs(D)) / (feather_px * w / W) + 0.5, 0, 1)


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
        swap_f = None; seam_pr = None; tail_frames = int(tail_s * fps)
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
                    seam_pr = seam(seg, cmap, maxmul, log=log)
                if swap_f is not None:
                    cB, wB, thB = (center - M["CM"]) / sig, w / abs(sig), theta - np.angle(sig)
                    a = min(1.0, (swap_f + 1) / fade); a = a * a * (3 - 2 * a)
                    m = patch_weight(cB, wB, thB, W, H, seam_pr) * a
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
            # advance the camera toward the dive target; on a handoff frame the camera is
            # already in the next world's coords, so step toward that segment's (nested) target
            tgt = segs[si + 1]["Q"] if done_seg and si + 1 < len(segs) else Q
            w *= rate
            center = tgt + (center - tgt) * rate
            if done_seg: break
    return recs, True
