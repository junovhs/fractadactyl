import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
import numpy as np
from fractadactyl import pert, minis
from fractadactyl.color import colorize
from PIL import Image
seed = complex(-0.743643887037151, 0.131825904205330)
W, H = 320, 240
T = complex(-0.7436438870371587, 0.1318259042053120)   # dive target in main-set coords
for r in (1e-4, 1e-3):
    m = minis.find(seed, r); p, s, Z = m['p'], m['s'], m['Z']
    print(f"== mini p={p} |s|={abs(s):.2e}")
    rows = []
    for w in [3.0, 0.3, 0.03, 3e-3, 3e-4, 3e-5]:
        f = 1 - w/3.0
        cen = complex(-0.75, 0)*(1-f) + T*f
        a, da = pert.render(*pert.MAIN, cen.real, cen.imag, w, 0.0, W, H, 50000, 1)
        d = s*cen
        b, db = pert.render(Z.real.copy(), Z.imag.copy(), d.real, d.imag, w*abs(s), np.angle(s), W, H, 50000*p, 1)
        mm = (a > 0) & (b > 0)
        A = np.polyfit(a[mm], b[mm], 1)
        agree = np.mean((a < 0) == (b < 0))
        ia = colorize(a*A[0] + A[1], da).astype(float)    # map main iterations onto mini's scale
        ib = colorize(b, db).astype(float)
        print(f"rel width {w:7.0e}: interior agree {agree*100:6.2f}%  nu_mini = {A[0]:6.2f} nu_main + {A[1]:8.1f}  colour MAE {np.abs(ia-ib).mean()/2.55:5.1f}%", flush=True)
        rows.append(np.concatenate([ia, ib], 1).astype(np.uint8))
    Image.fromarray(np.concatenate(rows, 0)).save(f'depthcheck_p{p}.png')
