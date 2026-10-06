//! Placeholder palette (PROD-01 / STUD-01 will make this a setting): hue from log(nu),
//! brightness from the pixel-normalised distance estimate, so the look is scale invariant.
use crate::pert::Samples;

/// (a, b) log-linear map of iteration counts: nu -> exp(a ln nu + b).
pub type NuMap = (f64, f64);
pub const IDENTITY: NuMap = (1.0, 0.0);

#[inline]
pub fn map_nu(nu: f64, ab: NuMap) -> f64 {
    if nu > 0.0 {
        (ab.0 * nu.ln() + ab.1).exp()
    } else {
        nu
    }
}

/// RGB8 image (h x w x 3), supersamples averaged before gamma.
pub fn colorize(s: &Samples, ab: NuMap, freq: f64) -> Vec<u8> {
    let n = s.n();
    let mut out = vec![0u8; s.w * s.h * 3];
    for px in 0..s.w * s.h {
        let mut acc = [0.0f64; 3];
        for k in 0..n {
            let nu = map_nu(s.nu[px * n + k], ab);
            if nu < 0.0 {
                continue; // inside: black
            }
            let t = nu.max(1.0).ln() * freq;
            let shade = (s.de[px * n + k] * 0.6).tanh().clamp(0.0, 1.0);
            for (c, ph) in [0.0, 0.15, 0.35].iter().enumerate() {
                acc[c] += (0.5 + 0.5 * (6.2832 * (t + ph)).cos()) * shade;
            }
        }
        for c in 0..3 {
            out[px * 3 + c] = ((acc[c] / n as f64).clamp(0.0, 1.0).powf(1.0 / 2.2) * 255.0) as u8;
        }
    }
    out
}
