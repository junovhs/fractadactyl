//! Twin library (LIB-01): validated island minis with a cheap lace signature; `pick` ranks
//! by signature distance, then fully scores the top K with `mismatch`.
use crate::color::{colorize, NuMap};
use crate::mandel::{nucleus, World, PATCH_C, PATCH_R};
use crate::mp::{bits_for, Mpc};
use num_complex::Complex64 as C64;
use rayon::prelude::*;
use serde::Deserialize;

pub const LIB_PATH: &str = "data/twins.json";
const SIG_WIDTHS: [f64; 3] = [40.0, 16.0, 9.0]; // the framings mismatch scores
const SIG_W: usize = 24;
const SIG_H: usize = 14;

#[derive(Deserialize, Clone)]
pub struct Twin {
    pub p: usize,
    pub s: [f64; 2],
    pub c0: String,
    pub valid: f64,
    pub sig: Vec<f32>,
}

impl Twin {
    pub fn world(&self) -> World {
        let size = C64::new(self.s[0], self.s[1]).norm();
        let prec = bits_for(size);
        let guess = Mpc::parse(&self.c0, prec);
        let c0 = nucleus(&guess, self.p, prec).unwrap_or(guess);
        World::from_nucleus(c0, self.p)
    }
}

pub fn load(path: &str) -> anyhow::Result<Vec<Twin>> {
    Ok(serde_json::from_reader(std::io::BufReader::new(std::fs::File::open(path)?))?)
}

/// Colour-map-free lace fingerprint: per framing, rank-normalised log iteration count
/// (interior = -1) and distance-estimate shading, at low resolution.
pub fn signature(x: &World) -> Vec<f32> {
    let mut out = Vec::new();
    for &w in &SIG_WIDTHS {
        let s = x.render(PATCH_C, w, 0.0, SIG_W, SIG_H, 1, 3000, None);
        let mut ext: Vec<(f64, usize)> = s.nu.iter().enumerate().filter(|(_, &v)| v > 0.0).map(|(i, &v)| (v.ln(), i)).collect();
        ext.sort_by(|a, b| a.0.total_cmp(&b.0));
        let mut rank = vec![-1.0f32; s.nu.len()];
        let denom = (ext.len().max(2) - 1) as f32;
        for (r, &(_, i)) in ext.iter().enumerate() {
            rank[i] = r as f32 / denom;
        }
        out.extend(rank);
        out.extend(s.de.iter().map(|&d| (d * 0.6).tanh() as f32));
    }
    out
}

fn soft_mask(w: f64, wpx: usize, hpx: usize, inner: f64) -> Vec<f64> {
    let px = w / wpx as f64;
    let mut m = Vec::with_capacity(wpx * hpx);
    for j in 0..hpx {
        for i in 0..wpx {
            let c = PATCH_C + C64::new((i as f64 + 0.5 - wpx as f64 / 2.0) * px, (j as f64 + 0.5 - hpx as f64 / 2.0) * px);
            let r = (c - PATCH_C).norm() / PATCH_R;
            let t = ((1.0 - r) / (1.0 - inner)).clamp(0.0, 1.0);
            m.push(t * t * (3.0 - 2.0 * t));
        }
    }
    m
}

fn percentile(sorted: &[f64], q: f64) -> f64 {
    let pos = q / 100.0 * (sorted.len() - 1) as f64;
    let (lo, hi) = (pos.floor() as usize, pos.ceil() as usize);
    sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo as f64)
}

/// Brightness continuity: a gain g on B's distance estimate so its edge shading has the
/// same median level as A's (log de quantiles 10..90, averaged difference).
pub fn fit_de_gain(de_a: &[f64], de_b: &[f64], nu_a: &[f64], nu_b: &[f64], mask: &[f64]) -> f64 {
    let (mut la, mut lb): (Vec<f64>, Vec<f64>) = (Vec::new(), Vec::new());
    for i in 0..mask.len() {
        if mask[i] > 0.5 && nu_a[i] > 0.0 && de_a[i] > 0.0 {
            la.push(de_a[i].ln());
        }
        if mask[i] > 0.5 && nu_b[i] > 0.0 && de_b[i] > 0.0 {
            lb.push(de_b[i].ln());
        }
    }
    if la.len() < 10 || lb.len() < 10 {
        return 1.0;
    }
    la.sort_by(f64::total_cmp);
    lb.sort_by(f64::total_cmp);
    let d: f64 = (1..10).map(|i| percentile(&la, 10.0 * i as f64) - percentile(&lb, 10.0 * i as f64)).sum::<f64>() / 9.0;
    d.exp().clamp(0.05, 20.0)
}

/// Appearance-only colour continuity: log(nuA) ~ a log(nuB) + b, fitted on quantiles.
pub fn fit_nu_map(nu_a: &[f64], nu_b: &[f64], mask: &[f64]) -> (f64, f64) {
    let (mut la, mut lb): (Vec<f64>, Vec<f64>) = (Vec::new(), Vec::new());
    for i in 0..mask.len() {
        if mask[i] > 0.5 && nu_a[i] > 0.0 && nu_b[i] > 0.0 {
            la.push(nu_a[i].ln());
            lb.push(nu_b[i].ln());
        }
    }
    if la.len() < 2 {
        return (1.0, 0.0);
    }
    la.sort_by(f64::total_cmp);
    lb.sort_by(f64::total_cmp);
    let qs: Vec<f64> = (0..49).map(|i| 2.0 + 2.0 * i as f64).collect();
    let xa: Vec<f64> = qs.iter().map(|&q| percentile(&lb, q)).collect();
    let ya: Vec<f64> = qs.iter().map(|&q| percentile(&la, q)).collect();
    let n = xa.len() as f64;
    let (mx, my) = (xa.iter().sum::<f64>() / n, ya.iter().sum::<f64>() / n);
    let sxy: f64 = xa.iter().zip(&ya).map(|(x, y)| (x - mx) * (y - my)).sum();
    let sxx: f64 = xa.iter().map(|x| (x - mx) * (x - mx)).sum();
    let a = if sxx > 0.0 { sxy / sxx } else { 1.0 };
    (a, my - a * mx)
}

/// How visible is A -> B at swap-ish scales? Composite vs real over three framings (%).
pub fn mismatch(a: &World, b: &World) -> (f64, NuMap) {
    let (w, h) = (192, 108);
    let fits: Vec<_> = [40.0, 16.0, 9.0]
        .iter()
        .map(|&wl| (a.render(PATCH_C, wl, 0.0, w, h, 2, 3000, None), b.render(PATCH_C, wl, 0.0, w, h, 2, 3000, None), soft_mask(wl, w, h, 0.6)))
        .collect();
    let mean = |v: &[f64], n: usize| -> Vec<f64> { v.chunks(n).map(|c| c.iter().sum::<f64>() / c.len() as f64).collect() };
    let (mut na, mut nb, mut da, mut db, mut mk) = (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new());
    for (sa, sb, m) in &fits {
        na.extend(mean(&sa.nu, sa.n()));
        nb.extend(mean(&sb.nu, sb.n()));
        da.extend(mean(&sa.de, sa.n()));
        db.extend(mean(&sb.de, sb.n()));
        mk.extend(m);
    }
    let (a, b0) = fit_nu_map(&na, &nb, &mk);
    let ab = (a, b0, fit_de_gain(&da, &db, &na, &nb, &mk));
    let mut total = 0.0;
    for (sa, sb, m) in &fits {
        let look = crate::color::Look::default();
        let real = colorize(sa, crate::color::IDENTITY, &look);
        let fake = colorize(sb, ab, &look);
        let mut acc = 0.0;
        for (i, mm) in m.iter().enumerate() {
            for c in 0..3 {
                let r = real[i * 3 + c] as f64;
                let comp = r * (1.0 - mm) + fake[i * 3 + c] as f64 * mm;
                acc += (comp - r).abs();
            }
        }
        total += acc / (m.len() * 3) as f64 / 2.55;
    }
    (total / 3.0, ab)
}

/// Best twin for `target`: signature shortlist, then full score. Excludes the target itself
/// and every world in `avoid` (recent worlds), so a chain never loops back into a world it
/// just left and visibly repeats.
pub fn pick(target: &World, lib: &[Twin], k: usize, avoid: &[&World]) -> Option<(World, f64, NuMap)> {
    let tsig = signature(target);
    let same = |t: &Twin, w: &World| t.p == w.p && (Mpc::parse(&t.c0, 64).to_c64() - w.c0.to_c64()).norm() < w.s.norm() * 1e-3;
    let pool: Vec<&Twin> = lib.iter().filter(|t| !same(t, target) && !avoid.iter().any(|w| same(t, w))).collect();
    let mut d: Vec<(f32, usize)> = pool
        .par_iter()
        .enumerate()
        .map(|(i, t)| (t.sig.iter().zip(&tsig).map(|(a, b)| (a - b) * (a - b)).sum::<f32>() / tsig.len() as f32, i))
        .collect();
    d.sort_by(|a, b| a.0.total_cmp(&b.0));
    let scored: Vec<(f64, usize, World, NuMap)> = d
        .iter()
        .take(k)
        .map(|&(_, i)| {
            let w = pool[i].world();
            let (e, ab) = mismatch(target, &w);
            (e, i, w, ab)
        })
        .collect();
    scored.into_iter().min_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1))).map(|(e, _, w, ab)| (w, e, ab))
}
