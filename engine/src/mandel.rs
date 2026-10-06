//! Minibrot geometry in high precision: ball-period search, nucleus Newton, the periodic
//! reference orbit and the mini's complex size (DEC-03).
use crate::mp::{f, Mpc};
use num_complex::Complex64 as C64;

/// Lowest n where the disc |c' - c| < r maps over 0 (Munafo/mathr ball method).
pub fn ball_period(c: &Mpc, r: f64, pmax: usize) -> Option<usize> {
    let prec = c.prec();
    let mut z = Mpc::zero(prec);
    let mut dz = Mpc::zero(prec);
    let one = Mpc::new(f(1.0, prec), f(0.0, prec));
    for n in 1..pmax {
        dz = z.mul(&dz).scale(2.0).add(&one);
        z = z.sqr().add(c);
        let az = z.abs();
        if az < dz.abs() * r {
            return Some(n);
        }
        if az > 4.0 {
            return None;
        }
    }
    None
}

/// Newton for z_p(c) = 0 starting at `guess`, at `prec` bits. Err if the derivative
/// vanishes (Newton landed on a lower-period nucleus).
pub fn nucleus(guess: &Mpc, p: usize, prec: usize) -> Result<Mpc, &'static str> {
    let mut c = guess.with_prec(prec);
    let one = Mpc::new(f(1.0, prec), f(0.0, prec));
    let tol = (-(prec as f64) + 16.0).exp2();
    for _ in 0..80 {
        let mut z = Mpc::zero(prec);
        let mut dz = Mpc::zero(prec);
        for i in 0..p {
            dz = z.mul(&dz).scale(2.0).add(&one);
            z = z.sqr().add(&c);
            // an escaping orbit squares itself past any exponent range: this guess is bad
            if i % 32 == 31 && !(z.abs() < 1e50) {
                return Err("orbit escaped");
            }
        }
        if dz.abs() == 0.0 {
            return Err("zero derivative");
        }
        let st = z.div(&dz);
        c = c.sub(&st);
        let a = st.abs();
        if !a.is_finite() {
            return Err("diverged");
        }
        if a < tol * c.abs().max(1e-300) || a == 0.0 {
            break;
        }
    }
    Ok(c)
}

/// Periodic orbit Z_0..Z_{p-1} (Z_0 = 0) in f64, plus the mini's complex size s
/// (c ~ c0 + s*C maps the main set onto the mini).
pub fn reference(c0: &Mpc, p: usize) -> (Vec<C64>, C64) {
    let prec = c0.prec();
    let mut zs = vec![C64::new(0.0, 0.0); p];
    let mut z = Mpc::zero(prec);
    let one = Mpc::new(f(1.0, prec), f(0.0, prec));
    let mut b = one.clone();
    let mut l = one.clone();
    for n in 1..p {
        z = z.sqr().add(c0);
        zs[n] = z.to_c64();
        l = z.mul(&l).scale(2.0);
        b = b.add(&l.inv());
    }
    let s = b.mul(&l).mul(&l).inv().to_c64();
    (zs, s)
}

/// A world: a minibrot whose local coordinates C map to c = c0 + s*C.
#[derive(Clone, Debug)]
pub struct World {
    pub p: usize,
    pub c0: Mpc,
    pub s: C64,
    pub z: Vec<C64>,
}

impl World {
    pub fn main() -> World {
        World { p: 1, c0: Mpc::zero(64), s: C64::new(1.0, 0.0), z: vec![C64::new(0.0, 0.0)] }
    }
    pub fn from_nucleus(c0: Mpc, p: usize) -> World {
        let (z, s) = reference(&c0, p);
        World { p, c0, s, z }
    }
}

/// Patch around a mini, in its own local coords (the mini is ~2.5 wide around -0.75).
pub const PATCH_C: C64 = C64 { re: -0.75, im: 0.0 };
pub const PATCH_R: f64 = 4.0;

impl World {
    /// Render a camera given in this world's local coords (centre, width, rotation).
    #[allow(clippy::too_many_arguments)]
    pub fn render(&self, center: C64, w: f64, theta: f64, wpx: usize, hpx: usize, ss: usize, maxmul: usize, need: Option<&[bool]>) -> crate::pert::Samples {
        crate::pert::render(&self.z, self.s * center, w * self.s.norm(), self.s.arg() + theta, wpx, hpx, maxmul * self.p, ss, need)
    }
}
