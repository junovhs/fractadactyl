# Fractadactyl

Endless-feeling Mandelbrot zoom videos at flat per-frame cost on a laptop, by faking depth
wherever a viewer can't tell. See [docs/FINDINGS.md](docs/FINDINGS.md).

## Layout
- `fractadactyl/` — renderer and tools
  - `pert.py` perturbation renderer referenced on a minibrot nucleus (periodic orbit)
  - `minis.py` find + validate island minibrots (`python -m fractadactyl.minis`)
  - `swap.py` local-coordinate worlds and swap compositing helpers
  - `twins.py` twin candidate search and mismatch scoring
  - `library.py` persistent twin library: `build` once, `pick` a matched twin in seconds
  - `color.py` placeholder palette (log-iteration hue + distance-estimate shading)
  - `mb.py` plain double renderer and ball-period helper
- `experiments/` — the scripts that produced each result
- `tests/blind/` — blind A/B clips (Git LFS) and their answer keys
- `data/` — saved search results

## Setup
```
pip install -r requirements.txt
git lfs pull
python -m fractadactyl.minis
python -m fractadactyl.library build --budget 0 --seed-from data/poc2_twins.pkl   # local twin library (data/twins.npz, not committed)
```
