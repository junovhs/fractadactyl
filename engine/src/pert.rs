//! Perturbation renderer whose reference is a minibrot NUCLEUS (DEC-03). The nucleus orbit
//! is exactly periodic, so the reference is p numbers reused forever: no per-frame
//! high-precision work at any depth.
use num_complex::Complex64 as C64;
use rayon::prelude::*;

const BAIL: f64 = 1e10;

/// Per-pixel samples: `nu` smooth iteration count (-1 inside), `de` distance estimate in
/// pixels, `ux, uy` the unit surface normal z/(dz/dc) in *screen* orientation (for 3D
/// slope lighting). Indexed [(j * w + i) * ss^2 + k].
pub struct Samples {
    pub w: usize,
    pub h: usize,
    pub ss: usize,
    pub nu: Vec<f64>,
    pub de: Vec<f64>,
    pub ux: Vec<f32>,
    pub uy: Vec<f32>,
}

impl Samples {
    pub fn n(&self) -> usize {
        self.ss * self.ss
    }
}

/// Newton for a period-P point of z -> z^2 + c from the orbit point (phase m0, delta x0).
/// True iff it converges to a cycle with multiplier |dz_P/dz_0| < 1: an attracting cycle
/// exists only for interior c, so the pixel is inside. Converges in a few steps even where
/// the orbit itself would take thousands of periods to settle.
fn attracting(zr: &[f64], zi: &[f64], m0: usize, mut x0r: f64, mut x0i: f64, ar: f64, ai: f64, period: usize) -> bool {
    let p = zr.len();
    let (mut first, mut prev) = (0.0, 0.0);
    for it in 0..12 {
        let (mut m, mut xr, mut xi) = (m0, x0r, x0i);
        let (mut dr, mut di) = (1.0f64, 0.0f64);
        for _ in 0..period {
            let (fr, fi) = (zr[m] + xr, zi[m] + xi);
            let t = 2.0 * (fr * dr - fi * di);
            di = 2.0 * (fr * di + fi * dr);
            dr = t;
            let t = 2.0 * zr[m] * xr - 2.0 * zi[m] * xi + xr * xr - xi * xi + ar;
            xi = 2.0 * zr[m] * xi + 2.0 * zi[m] * xr + 2.0 * xr * xi + ai;
            xr = t;
            m += 1;
            if m == p {
                m = 0;
            }
            let (fr, fi) = (zr[m] + xr, zi[m] + xi);
            if fr * fr + fi * fi > 4.0 {
                return false; // left the disc: not a cycle point
            }
            if fr * fr + fi * fi < xr * xr + xi * xi {
                xr = fr;
                xi = fi;
                m = 0;
            }
        }
        let rr = (zr[m] + xr) - (zr[m0] + x0r);
        let ri = (zi[m] + xi) - (zi[m0] + x0i); // f^P(z) - z
        let (er, ei) = (dr - 1.0, di);
        let den = er * er + ei * ei;
        if den == 0.0 || !den.is_finite() {
            return false;
        }
        let sr = (rr * er + ri * ei) / den;
        let si = (ri * er - rr * ei) / den; // step = r / (D - 1)
        x0r -= sr;
        x0i -= si;
        let st = sr.abs() + si.abs();
        if it == 0 {
            first = st;
        } else if st <= 1e-7 * first || st < 1e-300 {
            return dr * dr + di * di < 1.0;
        } else if it >= 2 && st > 0.5 * prev {
            return false; // not converging quadratically: wrong period
        }
        prev = st;
    }
    false
}

/// Iterate one sample; returns (nu, de_px, normal re, normal im) with the normal in c-plane
/// orientation.
#[inline]
fn sample(zr: &[f64], zi: &[f64], ar: f64, ai: f64, maxiter: usize, px: f64) -> (f64, f64, f64, f64) {
    let p = zr.len();
    let (mut xr, mut xi) = (0.0f64, 0.0f64); // delta z
    let (mut dr, mut di) = (0.0f64, 0.0f64); // dz/dc
    let (mut m, mut n) = (0usize, 0usize);
    let mut r2 = 0.0;
    let (mut szr, mut szi, mut chk) = (0.0f64, 0.0f64, 16usize);
    let mut newton_at = 64usize;
    let mut tries = 0;
    let mut esc = false;
    while n < maxiter {
        let (fr, fi) = (zr[m] + xr, zi[m] + xi); // full z_n
        let ndr = 2.0 * (fr * dr - fi * di) + 1.0;
        di = 2.0 * (fr * di + fi * dr);
        dr = ndr;
        // delta' = 2 Z delta + delta^2 + dc
        let t = 2.0 * zr[m] * xr - 2.0 * zi[m] * xi + xr * xr - xi * xi + ar;
        xi = 2.0 * zr[m] * xi + 2.0 * zi[m] * xr + 2.0 * xr * xi + ai;
        xr = t;
        m += 1;
        n += 1;
        if m == p {
            m = 0;
        }
        let (fr, fi) = (zr[m] + xr, zi[m] + xi);
        r2 = fr * fr + fi * fi;
        if r2 > BAIL {
            esc = true;
            break;
        }
        // rebase (Zhuoran): jump back to the reference start
        if r2 < xr * xr + xi * xi {
            xr = fr;
            xi = fi;
            m = 0;
        }
        let dz = (fr - szr).abs() + (fi - szi).abs();
        let sz = szr.abs() + szi.abs();
        if dz < 1e-13 * sz + 1e-300 {
            break;
        }
        // near-return to the saved point: candidate period n - chk/2; confirm by Newton
        if tries < 4 && n >= newton_at && dz < 1e-3 * sz {
            if attracting(zr, zi, m, xr, xi, ar, ai, n - chk / 2) {
                break;
            }
            tries += 1;
            newton_at = 4 * n;
        }
        if n == chk {
            szr = fr;
            szi = fi;
            chk *= 2;
        }
    }
    if esc {
        let lz = 0.5 * r2.ln();
        let nu = n as f64 + 1.0 - (lz / 2f64.ln()).ln() / 2f64.ln();
        let de = r2.sqrt() * lz / (dr * dr + di * di).sqrt() / px;
        // normal: u = z / (dz/dc), normalised
        let (fr, fi) = (zr[m] + xr, zi[m] + xi);
        let d2 = dr * dr + di * di;
        let (ur, ui) = ((fr * dr + fi * di) / d2, (fi * dr - fr * di) / d2);
        let un = (ur * ur + ui * ui).sqrt().max(1e-300);
        (nu, de, ur / un, ui / un)
    } else {
        (-1.0, 0.0, 0.0, 0.0)
    }
}

/// Render around reference `z`; `dc` is the view centre relative to the nucleus, `width`
/// in c units, `rot` radians. `need` (h x w) skips pixels nobody will see.
#[allow(clippy::too_many_arguments)]
pub fn render(z: &[C64], dc: C64, width: f64, rot: f64, w: usize, h: usize, maxiter: usize, ss: usize, need: Option<&[bool]>) -> Samples {
    let zr: Vec<f64> = z.iter().map(|c| c.re).collect();
    let zi: Vec<f64> = z.iter().map(|c| c.im).collect();
    let n = ss * ss;
    let px = width / w as f64;
    let (cr, sr) = (rot.cos(), rot.sin());
    let mut nu = vec![-1.0; w * h * n];
    let mut de = vec![0.0; w * h * n];
    let mut ux = vec![0.0f32; w * h * n];
    let mut uy = vec![0.0f32; w * h * n];
    nu.par_chunks_mut(w * n)
        .zip(de.par_chunks_mut(w * n))
        .zip(ux.par_chunks_mut(w * n).zip(uy.par_chunks_mut(w * n)))
        .enumerate()
        .for_each(|(j, ((nrow, drow), (xrow, yrow)))| {
        for i in 0..w {
            if let Some(nd) = need {
                if !nd[j * w + i] {
                    continue;
                }
            }
            for k in 0..n {
                let ox = (i as f64 + ((k % ss) as f64 + 0.5) / ss as f64 - w as f64 / 2.0) * px;
                let oy = (j as f64 + ((k / ss) as f64 + 0.5) / ss as f64 - h as f64 / 2.0) * px;
                let ar = dc.re + ox * cr - oy * sr; // Delta c
                let ai = dc.im + ox * sr + oy * cr;
                let (a, b, ur, ui) = sample(&zr, &zi, ar, ai, maxiter, px);
                nrow[i * n + k] = a;
                drow[i * n + k] = b;
                // rotate the normal from c-plane into screen orientation
                xrow[i * n + k] = (ur * cr + ui * sr) as f32;
                yrow[i * n + k] = (ui * cr - ur * sr) as f32;
            }
        }
    });
    Samples { w, h, ss, nu, de, ux, uy }
}
