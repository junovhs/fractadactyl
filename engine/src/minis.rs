//! Validate candidate minis against the main set: ball-period also finds satellite bulbs,
//! which are rejected below 97% shape agreement.
use crate::mandel::World;
use crate::pert;
use num_complex::Complex64 as C64;
use std::sync::OnceLock;

const VW: usize = 64;
const VH: usize = 48;

fn main_mask() -> &'static Vec<bool> {
    static M: OnceLock<Vec<bool>> = OnceLock::new();
    M.get_or_init(|| {
        let s = pert::render(&[C64::new(0.0, 0.0)], C64::new(-0.75, 0.0), 3.0, 0.0, VW, VH, 5000, 1, None);
        s.nu.iter().map(|&v| v < 0.0).collect()
    })
}

/// Fraction of a 64x48 view where the mini's interior agrees with the main set's.
pub fn validate(x: &World) -> f64 {
    let d = x.s * C64::new(-0.75, 0.0);
    let s = pert::render(&x.z, d, 3.0 * x.s.norm(), x.s.arg(), VW, VH, 5000 * x.p, 1, None);
    let m = main_mask();
    s.nu.iter().zip(m).filter(|(v, &mm)| (**v < 0.0) == mm).count() as f64 / m.len() as f64
}
