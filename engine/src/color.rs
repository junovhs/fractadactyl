//! Placeholder palette (PROD-01 / STUD-01 will make this a setting): hue from log(nu),
//! brightness from the pixel-normalised distance estimate, so the look is scale invariant.
use crate::pert::Samples;

/// How one world's samples are mapped to match another's look: (a, b) is the log-linear
/// map of iteration counts nu -> exp(a ln nu + b) (hue), g is a gain on the distance
/// estimate (edge-shading brightness).
pub type NuMap = (f64, f64, f64);
pub const IDENTITY: NuMap = (1.0, 0.0, 1.0);

#[inline]
pub fn map_nu(nu: f64, ab: NuMap) -> f64 {
    if nu > 0.0 {
        (ab.0 * nu.ln() + ab.1).exp()
    } else {
        nu
    }
}

/// Edge-shading brightness 0..1 from the pixel-normalised distance estimate.
#[inline]
pub fn brightness(de: f64, ab: NuMap) -> f64 {
    (de * ab.2 * 0.6).tanh().clamp(0.0, 1.0)
}

/// Relief style: `Smooth` lights the equipotential surface (polished folds); `Scallop`
/// lights a sawtooth height of the iteration count, so every iteration band becomes a
/// rounded shell with a crisp lip, and the bands flow over the geometry as the zoom moves.
#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Relief {
    Smooth,
    Scallop,
}

/// Look settings (a studio setting later, STUD-01).
#[derive(Clone, Debug)]
pub struct Look {
    pub stops: Vec<[f64; 3]>, // sRGB 0..1, cyclic
    pub freq: f64,            // palette cycles per e-fold of nu
    pub relief: Relief,
    pub bands: f64,     // scallop bands per e-fold of nu
    pub depth: f64,     // scallop relief strength
    pub light_deg: f64, // light direction on screen (0 = from the right, 90 = from below)
    pub elev_deg: f64,  // light elevation above the surface
    pub height: f64,    // Smooth relief: larger = flatter
    pub ambient: f64,
    pub specular: f64,
}

impl Look {
    pub fn umber() -> Look {
        Look {
            stops: vec![[0.16, 0.12, 0.10], [0.45, 0.37, 0.30], [0.78, 0.71, 0.62], [0.93, 0.91, 0.87], [0.55, 0.58, 0.66], [0.27, 0.31, 0.45]],
            freq: 0.35,
            relief: Relief::Smooth,
            bands: 6.0,
            depth: 1.0,
            light_deg: 225.0,
            elev_deg: 35.0,
            height: 1.2,
            ambient: 0.22,
            specular: 0.35,
        }
    }
    /// Near-monochrome warm bone with a hint of slate, scalloped (the user's reference clip).
    pub fn bone() -> Look {
        Look {
            stops: vec![[0.90, 0.88, 0.84], [0.80, 0.77, 0.72], [0.93, 0.92, 0.89], [0.70, 0.70, 0.72], [0.86, 0.84, 0.80]],
            freq: 0.08,
            relief: Relief::Scallop,
            bands: 64.0,
            depth: 1.5,
            light_deg: 225.0,
            elev_deg: 40.0,
            height: 1.2,
            ambient: 0.28,
            specular: 0.25,
        }
    }
    fn scalloped(stops: Vec<[f64; 3]>, freq: f64) -> Look {
        Look { stops, freq, ..Look::bone() }
    }
    pub const NAMES: [&'static str; 6] = ["bone", "umber", "copper", "twilight", "ember", "umber-smooth"];
    pub fn by_name(name: &str) -> Option<Look> {
        let hex = |h: u32| [((h >> 16) & 255) as f64 / 255.0, ((h >> 8) & 255) as f64 / 255.0, (h & 255) as f64 / 255.0];
        match name {
            "bone" => Some(Look::bone()),
            "umber-smooth" => Some(Look::umber()),
            "umber" => Some(Look { relief: Relief::Scallop, ..Look::umber() }), // the user's pick (2026-10-05)
            "copper" => Some(Look::scalloped([0x0f3b44, 0x2f7f86, 0xb87333, 0xe8c39e, 0xf4ecdc, 0x6a3d24].map(hex).to_vec(), 0.30)),
            "twilight" => Some(Look::scalloped([0x141a3c, 0x3b2f7a, 0x8a4f9e, 0xd9778e, 0xf2c57c, 0x6fa3c7].map(hex).to_vec(), 0.30)),
            "ember" => Some(Look::scalloped([0x1a0f0a, 0x6b1d0f, 0xc2491d, 0xf2a93b, 0xfbe7b5, 0x8c6d5a].map(hex).to_vec(), 0.30)),
            _ => None,
        }
    }
    fn palette(&self, t: f64) -> [f64; 3] {
        let n = self.stops.len() as f64;
        let x = t.rem_euclid(1.0) * n;
        let (i, f) = (x.floor() as usize % self.stops.len(), x - x.floor());
        let (a, b) = (self.stops[i], self.stops[(i + 1) % self.stops.len()]);
        let f = f * f * (3.0 - 2.0 * f); // smooth between stops
        [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
    }
}

impl Default for Look {
    fn default() -> Self {
        Look::by_name("umber").unwrap()
    }
}

/// Lighting factor and specular for one sample.
#[inline]
fn light(look: &Look, nu: f64, _de_px: f64, ux: f64, uy: f64, l: [f64; 3]) -> (f64, f64) {
    let d = match look.relief {
        Relief::Smooth => {
            let a = look.light_deg.to_radians();
            ((ux * a.cos() + uy * a.sin() + look.height) / (1.0 + look.height)).clamp(0.0, 1.0)
        }
        Relief::Scallop => {
            // height h = f(frac(B ln nu)) with f rounded: steep just past the lip, flat at the
            // crest. Each band gets the same relief however wide it is on screen (scale-free),
            // tilted along the surface normal u (nu grows toward the set).
            let x = (look.bands * nu.ln()).rem_euclid(1.0);
            let g = look.depth * 2.0 * (1.0 - x); // f(x) = 1 - (1 - x)^2
            let k = 1.0 / (1.0 + g * g).sqrt();
            ((ux * g * l[0] + uy * g * l[1]) * k + k * l[2]).clamp(0.0, 1.0)
        }
    };
    let lit = look.ambient + (1.0 - look.ambient) * d;
    (lit, look.specular * d.powi(24))
}

/// RGB8 image (h x w x 3): palette x 3D lighting, supersamples averaged in linear light.
pub fn colorize(s: &Samples, ab: NuMap, look: &Look) -> Vec<u8> {
    let n = s.n();
    let (a, e) = (look.light_deg.to_radians(), look.elev_deg.to_radians());
    let l = [a.cos() * e.cos(), a.sin() * e.cos(), e.sin()];
    let to_lin = |c: f64| c.powf(2.2);
    let mut out = vec![0u8; s.w * s.h * 3];
    for px in 0..s.w * s.h {
        let mut acc = [0.0f64; 3];
        for k in 0..n {
            let i = px * n + k;
            let nu = map_nu(s.nu[i], ab);
            if nu < 0.0 {
                continue; // inside: black
            }
            let nu = nu.max(1.0);
            let col = look.palette(nu.ln() * look.freq);
            // the colour map scales nu, so de (pixel distance) needs no adjustment here
            let (lit, spec) = light(look, nu, s.de[i] * ab.2, s.ux[i] as f64, s.uy[i] as f64, l);
            for c in 0..3 {
                acc[c] += to_lin(col[c]) * lit + spec;
            }
        }
        for c in 0..3 {
            out[px * 3 + c] = ((acc[c] / n as f64).clamp(0.0, 1.0).powf(1.0 / 2.2) * 255.0 + 0.5) as u8;
        }
    }
    out
}

/// Write an RGB8 buffer as PNG.
pub fn save_png(path: &std::path::Path, w: usize, h: usize, rgb: &[u8]) -> anyhow::Result<()> {
    let mut e = png::Encoder::new(std::io::BufWriter::new(std::fs::File::create(path)?), w as u32, h as u32);
    e.set_color(png::ColorType::Rgb);
    e.set_depth(png::BitDepth::Eight);
    e.write_header()?.write_image_data(rgb)?;
    Ok(())
}
