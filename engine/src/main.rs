//! `fz`: the fractadactyl command line (DEC-05).
//!
//!     fz chain --preview [--swaps N]          # 320x180 chain only: a quick look
//!     fz chain [--swaps 5] [--control-budget 2400]
//!
//! Writes <out>/: chain.mp4, chain_frames.mp4 (frame numbers burned in), answer.txt (swap
//! frames, for afterwards), timing.csv, timing.png, summary.txt; and control.mp4 unless
//! --preview. Frames go straight into ffmpeg; nothing is dumped to disk.
use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use fractadactyl::chain::{self, PlanOpts, Rec, RunOpts, Seg};
use fractadactyl::{library, mandel, mp::Mpc, pert};
use num_complex::Complex64 as C64;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};

#[derive(Parser)]
#[command(name = "fz", about = "Endless Mandelbrot zooms via hidden twin-minibrot swaps")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Plan and render a chained-swap zoom (and the real-depth control).
    Chain {
        #[arg(long)]
        swaps: Option<usize>,
        #[arg(long, default_value_t = 0)]
        seed: u64,
        /// 320x180, chain only, into <out>/preview
        #[arg(long)]
        preview: bool,
        /// twin period limit: bounds every frame's cost (DEC-04)
        #[arg(long, default_value_t = 64)]
        max_twin_p: usize,
        /// dive-target period limit: bounds the approach cost and keeps swaps between
        /// minis of similar lace density (DEC-04)
        #[arg(long, default_value_t = 600)]
        max_dive_p: usize,
        #[arg(long, default_value = "tests/blind/round4")]
        out: PathBuf,
        #[arg(long, default_value = library::LIB_PATH)]
        lib: String,
        /// seconds for control planning + rendering
        #[arg(long, default_value_t = 2400.0)]
        control_budget: f64,
        /// no terminal / live-frame windows
        #[arg(long)]
        no_live: bool,
    },
    /// Render one frame to raw f64 files (parity checks against the Python reference).
    Parity { c0: String, p: usize, cre: f64, cim: f64, w: f64, theta: f64, wpx: usize, hpx: usize, ss: usize, out: String },
}

const FONTS: [&str; 3] = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"];

fn font_path() -> Option<&'static str> {
    FONTS.iter().copied().find(|f| Path::new(f).exists())
}

/// ffmpeg reading raw RGB frames on stdin, upscaled to 1280x720.
fn encoder(w: usize, h: usize, mp4: &Path, with_numbers: bool) -> Result<Child> {
    let mut vf = "scale=1280:720:flags=lanczos".to_string();
    if with_numbers {
        let font = font_path().map(|f| format!("fontfile='{}':", f.replace(':', "\\:"))).unwrap_or_default();
        vf += &format!(",drawtext={font}text='frame %{{n}}':x=20:y=20:fontsize=36:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8");
    }
    Command::new("ffmpeg")
        .args(["-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", &format!("{w}x{h}"), "-framerate", "30", "-i", "-"])
        .args(["-vf", &vf, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p"])
        .arg(mp4)
        .stdin(Stdio::piped())
        .spawn()
        .context("starting ffmpeg")
}

/// Live view (when a display is available): a terminal window following the render log,
/// and an ffplay window showing each frame as it is rendered. Closing either never stops
/// the render.
struct Live {
    log: std::fs::File,
    player: Option<Child>,
}

impl Live {
    fn start(name: &str, out: &Path, w: usize, h: usize, show: bool) -> Result<Live> {
        let path = out.join(format!("{name}.log"));
        let log = std::fs::File::create(&path)?;
        let path = path.canonicalize()?; // the terminal starts in its own working directory
        let mut player = None;
        if show && std::env::var_os("DISPLAY").is_some() {
            let _ = Command::new("gnome-terminal")
                .args([&format!("--title=fz {name}"), "--geometry=130x30", "--", "bash", "-c"])
                .arg(format!("tail -n +1 -f '{}'", path.display()))
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();
            player = Command::new("ffplay")
                .args(["-loglevel", "quiet", "-window_title", &format!("fz {name} (live)"), "-f", "rawvideo", "-pixel_format", "rgb24"])
                .args(["-video_size", &format!("{w}x{h}"), "-framerate", "30", "-vf", "scale=960:540:flags=neighbor", "-i", "-"])
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .ok();
        }
        Ok(Live { log, player })
    }
    fn line(&mut self, s: &str) {
        let _ = writeln!(self.log, "{s}");
        eprintln!("{s}");
    }
    fn frame(&mut self, rgb: &[u8]) {
        if let Some(p) = &mut self.player {
            if p.stdin.as_mut().unwrap().write_all(rgb).is_err() {
                self.player = None; // window closed: keep rendering
            }
        }
    }
}

fn fmt_dur(s: f64) -> String {
    let s = s.max(0.0) as u64;
    if s >= 3600 { format!("{}h{:02}m", s / 3600, s / 60 % 60) } else { format!("{}m{:02}s", s / 60, s % 60) }
}

fn render_to(name: &str, segs: &[Seg], o: &RunOpts, mp4s: &[(PathBuf, bool)], out: &Path, live: bool) -> Result<(Vec<Rec>, bool)> {
    let mut encs: Vec<Child> = mp4s.iter().map(|(p, n)| encoder(o.w, o.h, p, *n)).collect::<Result<_>>()?;
    let total = chain::estimate_frames(segs, o).max(1);
    let nseg = segs.len();
    let live = std::cell::RefCell::new(Live::start(name, out, o.w, o.h, live)?);
    live.borrow_mut().line(&format!("== {name}: {} segments, ~{total} frames at {}x{} ss{}", nseg, o.w, o.h, o.ss));
    let t0 = std::time::Instant::now();
    let mut err = None;
    let (recs, done) = chain::run(
        segs,
        o,
        &mut |_, rgb| {
            for e in encs.iter_mut() {
                if let Err(x) = e.stdin.as_mut().unwrap().write_all(rgb) {
                    err.get_or_insert(x);
                }
            }
            live.borrow_mut().frame(rgb);
        },
        &mut |r| {
            let el = t0.elapsed().as_secs_f64();
            let left = total.saturating_sub(r.frame + 1).max(if r.frame + 1 >= total { 1 } else { 0 });
            let avg = el / (r.frame + 1) as f64;
            let frac = ((r.frame + 1) as f64 / total as f64).min(0.99);
            let bar: String = (0..30).map(|i| if (i as f64) < frac * 30.0 { '#' } else { '.' }).collect();
            live.borrow_mut().line(&format!(
                "[{bar}] {:3.0}%  frame {:5}/~{total}  seg {}/{} p={:<4} w={:.2e}  {:6.2}s/f  avg {:5.2}  elapsed {}  ETA ~{}{}",
                frac * 100.0, r.frame, r.seg, nseg - 1, r.world_p, r.width, r.secs, avg, fmt_dur(el), fmt_dur(left as f64 * avg),
                if r.swap_start { "  << SWAP STARTS" } else if r.swapping { "  (swap)" } else { "" }
            ));
        },
        &mut |m| live.borrow_mut().line(&format!("[{name}] {m}")),
    );
    if let Some(mut p) = live.borrow_mut().player.take() {
        drop(p.stdin.take()); // ffplay keeps showing the last frame until closed
        std::thread::spawn(move || p.wait());
    }
    for mut e in encs {
        drop(e.stdin.take());
        e.wait()?;
    }
    if let Some(e) = err {
        return Err(e.into());
    }
    live.borrow_mut().line(&format!("== DONE {name}: {} frames in {:.1} min, finished={done}", recs.len(), t0.elapsed().as_secs_f64() / 60.0));
    Ok((recs, done))
}

fn seg_means(recs: &[Rec]) -> Vec<(usize, f64, usize)> {
    let nseg = recs.iter().map(|r| r.seg).max().map_or(0, |m| m + 1);
    (0..nseg)
        .filter_map(|s| {
            let v: Vec<f64> = recs.iter().filter(|r| r.seg == s).map(|r| r.secs).collect();
            (!v.is_empty()).then(|| (s, v.iter().sum::<f64>() / v.len() as f64, v.len()))
        })
        .collect()
}

/// Per-frame render seconds for each series; dashed lines mark the chain's swap starts.
fn chart(series: &[(&str, &[Rec], plotters::style::RGBColor)], path: &Path) -> Result<()> {
    use plotters::prelude::*;
    if let Some(f) = font_path() {
        let bytes: &'static [u8] = Box::leak(std::fs::read(f)?.into_boxed_slice());
        let _ = plotters::style::register_font("sans-serif", FontStyle::Normal, bytes);
    }
    let root = BitMapBackend::new(path, (1200, 500)).into_drawing_area();
    root.fill(&WHITE)?;
    let n = series.iter().map(|s| s.1.len()).max().unwrap_or(1);
    let ymax = series.iter().flat_map(|s| s.1.iter().map(|r| r.secs)).fold(0.0, f64::max) * 1.05;
    let mut c = ChartBuilder::on(&root)
        .caption("render seconds per frame (dashed: swap starts)", ("sans-serif", 18))
        .margin(15)
        .x_label_area_size(35)
        .y_label_area_size(55)
        .build_cartesian_2d(0..n, 0.0..ymax.max(1e-3))?;
    c.configure_mesh().x_desc("frame").y_desc("seconds").draw()?;
    for (label, recs, col) in series {
        let col = *col;
        c.draw_series(LineSeries::new(recs.iter().map(|r| (r.frame, r.secs)), col.stroke_width(2)))?
            .label(*label)
            .legend(move |(x, y)| PathElement::new(vec![(x, y), (x + 20, y)], col));
    }
    if let Some((_, recs, col)) = series.first() {
        for r in recs.iter().filter(|r| r.swap_start) {
            let segs: Vec<_> = (0..20).map(|i| (i as f64 / 20.0 * ymax, (i as f64 + 0.5) / 20.0 * ymax)).collect();
            c.draw_series(segs.into_iter().map(|(a, b)| PathElement::new(vec![(r.frame, a), (r.frame, b)], *col)))?;
        }
    }
    c.configure_series_labels().border_style(BLACK).background_style(WHITE.mix(0.8)).draw()?;
    root.present()?;
    Ok(())
}

fn write_timing(path: &Path, series: &[(&str, &[Rec])]) -> Result<()> {
    let mut f = std::fs::File::create(path)?;
    writeln!(f, "series,frame,segment,seconds")?;
    for (name, recs) in series {
        for r in recs.iter() {
            writeln!(f, "{name},{},{},{:.4}", r.frame, r.seg, r.secs)?;
        }
    }
    Ok(())
}

fn main() -> Result<()> {
    match Cli::parse().cmd {
        Cmd::Chain { swaps, seed, preview, max_twin_p, max_dive_p, out, lib, control_budget, no_live } => {
            let swaps = swaps.unwrap_or(if preview { 1 } else { 5 });
            let out = if preview { out.join("preview") } else { out };
            std::fs::create_dir_all(&out)?;
            let mut ro = RunOpts::default();
            if preview {
                (ro.w, ro.h) = (320, 180);
            }
            let po = PlanOpts { swaps, seed, max_twin_p, max_dive_p, sigma_range: (1e-6, 1e-3) };
            let lib = library::load(&lib).with_context(|| format!("loading {lib} (export it with data/export_twins.py)"))?;

            eprintln!("== planning chain (twins, p <= {max_twin_p}, dive targets p <= {max_dive_p})");
            let t = std::time::Instant::now();
            let segs = chain::plan(Some(&lib), &po, &mut |m| eprintln!("{m}"));
            let plan_s = t.elapsed().as_secs_f64();
            let (recs, _) = render_to("chain", &segs, &ro, &[(out.join("chain.mp4"), false), (out.join("chain_frames.mp4"), true)], &out, !no_live)?;
            let swaps_at: Vec<String> = recs.iter().filter(|r| r.swap_start).map(|r| r.frame.to_string()).collect();
            std::fs::write(out.join("answer.txt"), format!("swap fade-in starts at frames: {}\n", swaps_at.join(", ")))?;

            let mut lines = vec![format!("chain: {} frames ({:.1} s), {} swaps, planning {plan_s:.0}s", recs.len(), recs.len() as f64 / 30.0, swaps_at.len())];
            lines.extend(seg_means(&recs).iter().map(|(s, m, n)| format!("  chain seg {s} (world p={}): mean {m:.3} s/frame over {n} frames", segs[*s].x.p)));
            lines.push(format!("  twin mismatch per swap: {}", segs.iter().filter(|s| s.m.is_some()).map(|s| format!("{:.2}%", s.err)).collect::<Vec<_>>().join(", ")));
            lines.push(format!("  dive-target period per swap: {}", segs.iter().filter_map(|s| s.m.as_ref().map(|m| m.w.p.to_string())).collect::<Vec<_>>().join(", ")));

            let mut control: Vec<Rec> = Vec::new();
            if !preview {
                eprintln!("== planning control (real nested minis, no twins)");
                let t = std::time::Instant::now();
                let csegs = chain::plan(None, &po, &mut |m| eprintln!("{m}"));
                let cplan = t.elapsed().as_secs_f64();
                let co = RunOpts { budget_s: Some(control_budget), ..RunOpts::default() };
                let (crecs, cdone) = render_to("control", &csegs, &co, &[(out.join("control.mp4"), false)], &out, !no_live)?;
                lines.push(format!("control: {} frames, finished={cdone}, planning {cplan:.0}s for {} nested minis", crecs.len(), csegs.len() - 1));
                lines.extend(seg_means(&crecs).iter().map(|(s, m, n)| format!("  control seg {s} (world p={}): mean {m:.3} s/frame over {n} frames", csegs[*s].x.p)));
                control = crecs;
            }
            write_timing(&out.join("timing.csv"), &[("chain", &recs), ("control", &control)])?;
            let mut series = vec![("chain (hidden swaps)", recs.as_slice(), plotters::style::RGBColor(31, 119, 180))];
            if !control.is_empty() {
                series.push(("control (real depth, no swaps)", control.as_slice(), plotters::style::RGBColor(214, 39, 40)));
            }
            chart(&series, &out.join("timing.png"))?;
            std::fs::write(out.join("summary.txt"), lines.join("\n") + "\n")?;
            println!("{}", lines.join("\n"));
        }
        Cmd::Parity { c0, p, cre, cim, w, theta, wpx, hpx, ss, out } => {
            let world = if c0 == "main" {
                mandel::World::main()
            } else {
                let c = mandel::nucleus(&Mpc::parse(&c0, 400), p, 400).map_err(anyhow::Error::msg)?;
                mandel::World::from_nucleus(c, p)
            };
            let t = std::time::Instant::now();
            let s = pert::render(&world.z, world.s * C64::new(cre, cim), w * world.s.norm(), world.s.arg() + theta, wpx, hpx, 5000 * world.p, ss, None);
            eprintln!("p={} render {:.3}s", world.p, t.elapsed().as_secs_f64());
            for (suffix, v) in [("nu", &s.nu), ("de", &s.de)] {
                let bytes: Vec<u8> = v.iter().flat_map(|x| x.to_le_bytes()).collect();
                std::fs::write(format!("{out}_{suffix}.f64"), bytes)?;
            }
            println!("{} {} {}", world.s.re, world.s.im, world.c0.to_string());
        }
    }
    Ok(())
}
