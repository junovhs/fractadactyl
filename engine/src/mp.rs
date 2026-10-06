//! Arbitrary-precision complex numbers for planning (nuclei, reference orbits, sizes).
//! Only per-mini work runs here; the per-pixel loop never touches it (DEC-03, DEC-05).
use dashu_float::{DBig, FBig};
use num_complex::Complex64 as C64;
use std::str::FromStr;

pub type F = FBig;

/// Bits for a world of complex size |s| (the prototype used max(40, -log10|s| + 30) digits).
pub fn bits_for(size: f64) -> usize {
    let digits = (-(size.abs().log10())).max(0.0) as usize + 30;
    (digits.max(40) as f64 * 3.33) as usize + 8
}

pub fn f(x: f64, prec: usize) -> F {
    F::try_from(x).unwrap().with_precision(prec).value()
}

pub fn parse(s: &str, prec: usize) -> F {
    DBig::from_str(s.trim())
        .expect("decimal number")
        .with_base_and_precision::<2>(prec)
        .value()
        .with_rounding()
}

#[derive(Clone, Debug)]
pub struct Mpc {
    pub re: F,
    pub im: F,
}

impl Mpc {
    pub fn new(re: F, im: F) -> Self {
        Mpc { re, im }
    }
    pub fn zero(prec: usize) -> Self {
        Mpc::new(f(0.0, prec), f(0.0, prec))
    }
    pub fn from_c64(c: C64, prec: usize) -> Self {
        Mpc::new(f(c.re, prec), f(c.im, prec))
    }
    /// "(a+bj)", "a+bj", "a-bj" as written by Python's str(mpc) or complex.
    pub fn parse(s: &str, prec: usize) -> Self {
        let t: String = s.chars().filter(|c| !c.is_whitespace() && *c != '(' && *c != ')').collect();
        let t = t.trim_end_matches('j');
        // split at the sign that starts the imaginary part (not an exponent sign, not position 0)
        let b = t.as_bytes();
        let mut cut = None;
        for i in (1..b.len()).rev() {
            if (b[i] == b'+' || b[i] == b'-') && b[i - 1] != b'e' && b[i - 1] != b'E' {
                cut = Some(i);
                break;
            }
        }
        let i = cut.expect("complex literal");
        Mpc::new(parse(&t[..i], prec), parse(&t[i..], prec))
    }
    pub fn prec(&self) -> usize {
        self.re.precision()
    }
    pub fn with_prec(&self, prec: usize) -> Self {
        Mpc::new(self.re.clone().with_precision(prec).value(), self.im.clone().with_precision(prec).value())
    }
    pub fn to_c64(&self) -> C64 {
        C64::new(self.re.to_f64().value(), self.im.to_f64().value())
    }
    pub fn add(&self, o: &Mpc) -> Mpc {
        Mpc::new(&self.re + &o.re, &self.im + &o.im)
    }
    pub fn sub(&self, o: &Mpc) -> Mpc {
        Mpc::new(&self.re - &o.re, &self.im - &o.im)
    }
    pub fn mul(&self, o: &Mpc) -> Mpc {
        Mpc::new(&self.re * &o.re - &self.im * &o.im, &self.re * &o.im + &self.im * &o.re)
    }
    pub fn sqr(&self) -> Mpc {
        let two = &self.re * &self.im;
        Mpc::new(&self.re * &self.re - &self.im * &self.im, &two + &two)
    }
    pub fn scale(&self, k: f64) -> Mpc {
        let k = f(k, self.prec());
        Mpc::new(&self.re * &k, &self.im * &k)
    }
    pub fn div(&self, o: &Mpc) -> Mpc {
        let d = &o.re * &o.re + &o.im * &o.im;
        Mpc::new(
            (&self.re * &o.re + &self.im * &o.im) / &d,
            (&self.im * &o.re - &self.re * &o.im) / &d,
        )
    }
    pub fn inv(&self) -> Mpc {
        let d = &self.re * &self.re + &self.im * &self.im;
        Mpc::new(&self.re / &d, -(&self.im / &d))
    }
    /// |z| as f64: magnitudes in planning stay well inside f64 range.
    pub fn abs(&self) -> f64 {
        self.to_c64().norm()
    }
    /// |z| with exponent-safe evaluation when f64 would underflow.
    pub fn abs_log2(&self) -> f64 {
        let r = self.re.to_f64().value();
        let i = self.im.to_f64().value();
        (r * r + i * i).sqrt().log2()
    }
    pub fn to_string(&self) -> String {
        format!("({}{}{}j)", self.re.to_decimal().value(), if self.im.sign() == dashu_base::Sign::Negative { "" } else { "+" }, self.im.to_decimal().value())
    }
}
