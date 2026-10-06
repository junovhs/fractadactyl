//! Chained hidden swaps (POC-02, DEC-02).
//!
//! A *world* X is a minibrot whose local coordinates C map to c = c0 + s*C, so every world
//! looks like the main set at C. The camera (centre, width, rotation) lives in the current
//! world's local coords. Each segment dives toward a sub-minibrot M found ahead inside X;
//! when M's patch is a few pixels wide, a library twin B (a shallow look-alike of M) fades in
//! inside an optimal seam, and once the seam covers the screen the camera is re-expressed in
//! B's local coords and B becomes the current world. True depth never accumulates. Without a
//! library the "twin" is M itself: the real, ever-deeper control path.
//!
//! Per-frame cost is proportional to the current world's period and to the period of the
//! mini being approached, so both are capped (DEC-04).
use crate::color::{colorize, NuMap, IDENTITY};
use crate::library::{self, Twin};
use crate::mandel::{ball_period, nucleus, World, PATCH_C, PATCH_R};
use crate::minis;
use crate::mp::{bits_for, Mpc};
use num_complex::Complex64 as C64;
use rand::seq::SliceRandom;
use rand::SeedableRng;
use std::f64::consts::PI;
use std::time::Instant;

const SEAM_R: (f64, f64) = (1.5, 3.9); // seam may wander between these radii (mini-local)
const SEAM_N: usize = 512; // seam-cost render size (pixels across the patch)
const FREQ: f64 = 1.5;

fn dive_points() -> Vec<C64> {
    let base = [
        C64::new(-0.7436438870371587, 0.1318259042053120), // seahorse valley
        C64::new(-1.2537, 0.0384),                          // west tendril
        C64::new(-0.10109636384562, 0.95628651080914),      // upper antenna
        C64::new(0.4245, 0.2075),                           // east rim
        C64::new(-0.7746806106269039, 0.1374168856037867),  // seahorse, second
    ];
    base.iter().copied().chain(base.iter().map(|p| p.conj())).collect() // mirror images work too
}

/// A sub-mini M of world X: its own world, size relative to X (sigma) and centre in X-local.
#[derive(Clone)]
pub struct Mini {
    pub w: World,
    pub sigma: C64,
    pub cm: C64,
}

#[derive(Clone)]
pub struct Seg {
    pub x: World,
    pub m: Option<Mini>,
    pub b: Option<World>,
    pub ab: NuMap,
    pub err: f64,
    pub q: C64, // dive target in X-local coords (nested through every later segment)
}

#[derive(Clone, Copy)]
pub struct PlanOpts {
    pub swaps: usize,
    pub seed: u64,
    pub max_twin_p: usize,
    pub max_dive_p: usize,
    pub sigma_range: (f64, f64),
}

/// A validated island minibrot near X-local point P, relative size in range, period capped.
pub fn find_sub_mini(x: &World, p_local: C64, o: &PlanOpts) -> Option<Mini> {
    let prec = bits_for(x.s.norm() * o.sigma_range.0);
    let cx = x.c0.with_prec(prec);
    let sx = Mpc::from_c64(x.s, prec);
    let cp = cx.add(&sx.mul(&Mpc::from_c64(p_local, prec)));
    for j in 2..10 {
        let r = x.s.norm() * 10f64.powi(-j);
        let Some(p) = ball_period(&cp, r, o.max_dive_p + 1) else { continue };
        if p <= x.p {
            continue;
        }
        let Ok(c0) = nucleus(&cp, p, prec) else { continue };
        let cm = c0.sub(&cx).div(&sx).to_c64();
        let w = World::from_nucleus(c0, p);
        let sigma = w.s / x.s;
        if !(o.sigma_range.0..=o.sigma_range.1).contains(&sigma.norm()) || (cm - p_local).norm() > 0.5 {
            continue;
        }
        if minis::validate(&w) < 0.97 {
            continue;
        }
        return Some(Mini { w, sigma, cm });
    }
    None
}

/// Try dive points in random order; if none has a sub-mini under the period cap, retry once
/// with the cap doubled (a few worlds have nothing small enough near any dive point).
fn find_with_fallback(x: &World, rng: &mut impl rand::Rng, o: &PlanOpts) -> Option<(C64, Mini)> {
    let mut pts = dive_points();
    pts.shuffle(rng);
    let relaxed = PlanOpts { max_dive_p: o.max_dive_p * 2, ..*o };
    let found = [o, &relaxed].into_iter().find_map(|oo| pts.iter().find_map(|&p| find_sub_mini(x, p, oo).map(|m| (p, m))));
    found
}

/// Plan segments. `lib` None plans the real control path (twin = the mini itself).
pub fn plan(lib: Option<&[Twin]>, o: &PlanOpts, log: &mut dyn FnMut(String)) -> Vec<Seg> {
    let lib: Option<Vec<Twin>> = lib.map(|l| l.iter().filter(|t| t.p <= o.max_twin_p).cloned().collect());
    let mut rng = rand_chacha::ChaCha8Rng::seed_from_u64(o.seed);
    let t0 = Instant::now();
    let mut x = World::main();
    let mut segs = Vec::new();
    let mut cur = find_with_fallback(&x, &mut rng, o);
    let mut last_p = cur.as_ref().map(|c| c.0).unwrap_or(dive_points()[0]);
    let mut recent: Vec<World> = vec![x.clone()]; // worlds a twin must not be (no visible loops)
    for k in 0..o.swaps {
        let Some((_, m)) = cur.take() else {
            log(format!("  chain stops at {k} swaps"));
            break;
        };
        let (b, err, ab) = match &lib {
            Some(l) => match library::pick(&m.w, l, 16, &recent.iter().collect::<Vec<_>>()) {
                Some(t) => t,
                None => break,
            },
            None => (m.w.clone(), 0.0, IDENTITY),
        };
        let next = if k + 1 < o.swaps { find_with_fallback(&b, &mut rng, o) } else { None };
        last_p = next.as_ref().map(|n| n.0).unwrap_or(dive_points()[0]);
        log(format!(
            "  seg {k}: world p={} |s|={:.1e} -> mini p={} |sigma|={:.1e}  twin p={} |s|={:.1e} mismatch {:.2}%  ({:.0}s)",
            x.p, x.s.norm(), m.w.p, m.sigma.norm(), b.p, b.s.norm(), err, t0.elapsed().as_secs_f64()
        ));
        segs.push(Seg { x: x.clone(), m: Some(m), b: Some(b.clone()), ab, err, q: C64::new(0.0, 0.0) });
        x = b;
        recent.push(x.clone());
        if recent.len() > 4 {
            recent.remove(0);
        }
        cur = next;
    }
    segs.push(Seg { x, m: None, b: None, ab: IDENTITY, err: 0.0, q: last_p });
    // aim the whole chain at one nested point: segment k's target is segment k+1's target
    // seen through M_k (B-local ~ M-local), so the zoom's fixed point never jumps at a handoff
    for k in (0..segs.len() - 1).rev() {
        let m = segs[k].m.as_ref().unwrap();
        segs[k].q = m.cm + m.sigma * segs[k + 1].q;
    }
    segs
}

fn compose(cmap: NuMap, ab: NuMap) -> NuMap {
    (cmap.0 * ab.0, cmap.0 * ab.1 + cmap.1)
}

/// Optimal seam (panorama-stitching style): a closed curve r(phi) around the incoming mini,
/// in its local polar coords, along which X and the twin B look most alike. Computed once
/// per swap, so it is fixed in world space and zooms with it.
pub fn seam(seg: &Seg, cmap: NuMap, maxmul: usize, log: &mut dyn FnMut(String)) -> (Vec<f64>, Vec<f64>) {
    let (n_ang, n_rad, bend) = (720usize, 96usize, 0.05);
    let t0 = Instant::now();
    let (m, b) = (seg.m.as_ref().unwrap(), seg.b.as_ref().unwrap());
    let (n, r_max) = (SEAM_N, SEAM_R.1);
    let cmap_b = compose(cmap, seg.ab);
    let sx = seg.x.render(m.cm + m.sigma * PATCH_C, 2.0 * r_max * m.sigma.norm(), m.sigma.arg(), n, n, 1, maxmul, None);
    let sb = b.render(PATCH_C, 2.0 * r_max, 0.0, n, n, 1, maxmul, None);
    let hue = |nu: f64, ab: NuMap| if nu > 0.0 { Some((ab.0 * nu.ln() + ab.1) * FREQ) } else { None };
    let diff: Vec<f64> = (0..n * n)
        .map(|i| match (hue(sx.nu[i], cmap), hue(sb.nu[i], cmap_b)) {
            (Some(a), Some(b)) => 1.0 - (2.0 * PI * (a - b)).cos(),
            (None, None) => 0.0,
            _ => 4.0, // inside vs outside: worst
        })
        .collect();
    let phi: Vec<f64> = (0..n_ang).map(|a| 2.0 * PI * a as f64 / n_ang as f64).collect();
    let rad: Vec<f64> = (0..n_rad).map(|r| SEAM_R.0 + (r_max * 0.98 - SEAM_R.0) * r as f64 / (n_rad - 1) as f64).collect();
    let cost: Vec<Vec<f64>> = phi
        .iter()
        .map(|&ph| {
            rad.iter()
                .map(|&r| {
                    let (x, y) = (r * ph.cos(), r * ph.sin());
                    let ix = (((x + r_max) / (2.0 * r_max) * n as f64) as usize).min(n - 1);
                    let iy = (((y + r_max) / (2.0 * r_max) * n as f64) as usize).min(n - 1);
                    diff[iy * n + ix]
                })
                .collect()
        })
        .collect();
    // closed-loop DP: radius index moves by <= 1 per angle step (each move costs `bend`, so
    // the seam stays smooth); try every other start radius
    let mut best = (f64::INFINITY, Vec::new());
    for r0 in (0..n_rad).step_by(2) {
        let mut acc = vec![f64::INFINITY; n_rad];
        acc[r0] = cost[0][r0];
        let mut back = vec![vec![0i8; n_rad]; n_ang];
        for a in 1..n_ang {
            let mut nacc = vec![f64::INFINITY; n_rad];
            for r in 0..n_rad {
                let mut bv = acc[r];
                let mut bj = 0i8;
                if r > 0 && acc[r - 1] + bend < bv {
                    bv = acc[r - 1] + bend;
                    bj = -1;
                }
                if r + 1 < n_rad && acc[r + 1] + bend < bv {
                    bv = acc[r + 1] + bend;
                    bj = 1;
                }
                back[a][r] = bj;
                nacc[r] = bv + cost[a][r];
            }
            acc = nacc;
        }
        let e = [r0 as isize - 1, r0 as isize, r0 as isize + 1]
            .into_iter()
            .filter(|&r| r >= 0 && (r as usize) < n_rad)
            .map(|r| r as usize)
            .min_by(|&a, &b| acc[a].total_cmp(&acc[b]))
            .unwrap();
        if acc[e] < best.0 {
            let mut path = vec![0usize; n_ang];
            path[n_ang - 1] = e;
            for a in (1..n_ang).rev() {
                path[a - 1] = (path[a] as isize + back[a][path[a]] as isize) as usize;
            }
            best = (acc[e], path);
        }
    }
    let r_phi: Vec<f64> = best.1.iter().map(|&i| rad[i]).collect();
    let circle = (0..n_rad).map(|r| cost.iter().map(|c| c[r]).sum::<f64>() / n_ang as f64).fold(f64::INFINITY, f64::min);
    log(format!(
        "  seam: mean cost {:.3} (straight circle {:.3}), r {:.2}..{:.2}  ({:.1}s)",
        best.0 / n_ang as f64,
        circle,
        r_phi.iter().cloned().fold(f64::INFINITY, f64::min),
        r_phi.iter().cloned().fold(0.0, f64::max),
        t0.elapsed().as_secs_f64()
    ));
    (phi, r_phi)
}

/// Patch mask for a camera in the incoming mini's local coords: 1 inside the seam, 0
/// outside, feathered over a few *screen* pixels.
fn patch_weight(center: C64, w: f64, theta: f64, wpx: usize, hpx: usize, seam: &(Vec<f64>, Vec<f64>), feather_px: f64) -> Vec<f64> {
    let (phi, r_phi) = seam;
    let n = phi.len();
    let px = w / wpx as f64;
    let rot = C64::from_polar(1.0, theta);
    let mut out = Vec::with_capacity(wpx * hpx);
    for j in 0..hpx {
        for i in 0..wpx {
            let d = center - PATCH_C + C64::new((i as f64 + 0.5 - wpx as f64 / 2.0) * px, (j as f64 + 0.5 - hpx as f64 / 2.0) * px) * rot;
            let a = d.arg().rem_euclid(2.0 * PI) / (2.0 * PI) * n as f64;
            let (i0, t) = (a.floor() as usize % n, a - a.floor());
            let rs = r_phi[i0] * (1.0 - t) + r_phi[(i0 + 1) % n] * t;
            out.push(((rs - d.norm()) / (feather_px * px) + 0.5).clamp(0.0, 1.0));
        }
    }
    out
}

pub struct RunOpts {
    pub w: usize,
    pub h: usize,
    pub ss: usize,
    pub fps: f64,
    pub dec_per_s: f64,
    pub swap_px: f64,
    pub fade: usize,
    pub tail_s: f64,
    pub maxmul: usize,
    pub budget_s: Option<f64>,
}

impl Default for RunOpts {
    fn default() -> Self {
        RunOpts { w: 640, h: 360, ss: 2, fps: 30.0, dec_per_s: 0.6, swap_px: 6.0, fade: 10, tail_s: 3.0, maxmul: 5000, budget_s: None }
    }
}

pub struct Rec {
    pub frame: usize,
    pub seg: usize,
    pub secs: f64,
    pub swap_start: bool,
    pub swapping: bool,
    pub world_p: usize,
    pub width: f64,
}

/// Frame count from a dry run of the camera (no rendering); the seam's smallest radius
/// stands in for the real seam when deciding that the patch covers the screen.
pub fn estimate_frames(segs: &[Seg], o: &RunOpts) -> usize {
    let rate = 10f64.powf(-o.dec_per_s / o.fps);
    let (mut center, mut w, mut theta) = (C64::new(-0.6, 0.0), 3.5, 0.0);
    let mut k = 0;
    for (si, seg) in segs.iter().enumerate() {
        let Some(m) = &seg.m else {
            return k + (o.tail_s * o.fps) as usize;
        };
        loop {
            k += 1;
            let mut done = false;
            if 2.0 * PATCH_R * m.sigma.norm() / w * o.w as f64 >= o.swap_px {
                let (cb, wb) = ((center - m.cm) / m.sigma, w / m.sigma.norm());
                let half = (wb / 2.0) * C64::new(1.0, o.h as f64 / o.w as f64).norm();
                if (cb - PATCH_C).norm() + half < SEAM_R.0 {
                    (center, w, theta) = (cb, wb, theta - m.sigma.arg());
                    done = true;
                }
            }
            let tgt = if done { segs[si + 1].q } else { seg.q };
            w *= rate;
            center = tgt + (center - tgt) * rate;
            if done || k > 100_000 {
                break;
            }
        }
    }
    let _ = theta;
    k
}

/// Render the chain; `out_frame(k, rgb)` consumes each frame. Returns (records, finished).
pub fn run(
    segs: &[Seg],
    o: &RunOpts,
    out_frame: &mut dyn FnMut(usize, &[u8]),
    progress: &mut dyn FnMut(&Rec),
    log: &mut dyn FnMut(String),
) -> (Vec<Rec>, bool) {
    let rate = 10f64.powf(-o.dec_per_s / o.fps);
    let (mut center, mut w, mut theta) = (C64::new(-0.6, 0.0), 3.5, 0.0);
    let mut cmap = IDENTITY;
    let mut recs = Vec::new();
    let mut k = 0usize;
    let t_start = Instant::now();
    for (si, seg) in segs.iter().enumerate() {
        let mut swap_f: Option<usize> = None;
        let mut seam_pr = None;
        let mut tail = (o.tail_s * o.fps) as usize;
        loop {
            if o.budget_s.is_some_and(|b| t_start.elapsed().as_secs_f64() > b) {
                log(format!("  render budget hit at frame {k}"));
                return (recs, false);
            }
            let t0 = Instant::now();
            let mut done = false;
            let mut started = false;
            let mut mask: Option<Vec<f64>> = None;
            let mut cam_b = (C64::new(0.0, 0.0), 0.0, 0.0);
            let mut alpha = 0.0;
            if let Some(m) = &seg.m {
                if swap_f.is_none() && 2.0 * PATCH_R * m.sigma.norm() / w * o.w as f64 >= o.swap_px {
                    swap_f = Some(0);
                    started = true;
                    seam_pr = Some(seam(seg, cmap, o.maxmul, log));
                }
                if let Some(f) = swap_f {
                    cam_b = ((center - m.cm) / m.sigma, w / m.sigma.norm(), theta - m.sigma.arg());
                    let a = ((f + 1) as f64 / o.fade as f64).min(1.0);
                    alpha = a * a * (3.0 - 2.0 * a);
                    let pw = patch_weight(cam_b.0, cam_b.1, cam_b.2, o.w, o.h, seam_pr.as_ref().unwrap(), 2.5);
                    mask = Some(pw.into_iter().map(|v| v * alpha).collect());
                }
            }
            // only render each world where it is visible: X outside the solid patch, B inside
            let need_x: Option<Vec<bool>> = mask.as_ref().map(|m| m.iter().map(|&v| v < 1.0).collect());
            let sx = seg.x.render(center, w, theta, o.w, o.h, o.ss, o.maxmul, need_x.as_deref());
            let mut rgb = colorize(&sx, cmap, FREQ);
            if let Some(m) = &mask {
                let cmap_b = compose(cmap, seg.ab);
                let need_b: Vec<bool> = m.iter().map(|&v| v > 0.0).collect();
                let sb = seg.b.as_ref().unwrap().render(cam_b.0, cam_b.1, cam_b.2, o.w, o.h, o.ss, o.maxmul, Some(&need_b));
                let rgb_b = colorize(&sb, cmap_b, FREQ);
                for (i, &mm) in m.iter().enumerate() {
                    for c in 0..3 {
                        let v = rgb[i * 3 + c] as f64 * (1.0 - mm) + rgb_b[i * 3 + c] as f64 * mm;
                        rgb[i * 3 + c] = v as u8;
                    }
                }
                *swap_f.as_mut().unwrap() += 1;
                if alpha >= 1.0 && m.iter().all(|&v| v >= 1.0) {
                    // patch covers the screen: continue in the twin's coords
                    (center, w, theta) = cam_b;
                    cmap = cmap_b;
                    done = true;
                }
            } else if seg.m.is_none() {
                tail -= 1;
                done = tail == 0;
            }
            out_frame(k, &rgb);
            let secs = t0.elapsed().as_secs_f64();
            recs.push(Rec { frame: k, seg: si, secs, swap_start: started, swapping: mask.is_some(), world_p: seg.x.p, width: w });
            progress(recs.last().unwrap());
            k += 1;
            // advance toward the dive target; on a handoff frame the camera is already in the
            // next world's coords, so step toward that segment's (nested) target
            let tgt = if done && si + 1 < segs.len() { segs[si + 1].q } else { seg.q };
            w *= rate;
            center = tgt + (center - tgt) * rate;
            if done {
                break;
            }
        }
    }
    (recs, true)
}
