import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
import numpy as np
from PIL import Image
from fractadactyl.swap import *; from fractadactyl.color import colorize
A, B = load_worlds()
W, H, ss = 640, 360, 2
T = complex(-0.7436438870371587, 0.1318259042053120)
rows = []
for f in (0.01, 0.03, 0.05, 0.10):
    w = 2*PATCH_R / f                 # patch diameter = f of screen width
    cen = T
    nA, dA = render_world(A, cen, w, W, H, ss)
    nB, dB = render_world(B, cen, w, W, H, ss)
    mk = patch_mask(cen, w, W, H)
    ab = fit_nu_map(nA.mean(2), nB.mean(2), mk)
    nB2 = apply_nu_map(nB, ab)
    real = colorize(nA, dA, freq=1.5).astype(float)
    fakeB = colorize(nB2, dB, freq=1.5).astype(float)
    comp = real*(1-mk[..., None]) + fakeB*mk[..., None]
    diff = np.abs(comp - real).mean(2)
    inpatch = diff[mk > 0.5].mean()/2.55
    frame = diff.mean()/2.55
    print(f"patch = {f*100:4.0f}% of width: mean colour change inside patch {inpatch:5.1f}%, whole frame {frame:5.2f}%, pixels changed >10%: {(diff>25.5).mean()*100:5.2f}%", flush=True)
    rows.append(np.concatenate([real, comp], 1).astype(np.uint8))
Image.fromarray(np.concatenate(rows, 0)).save('measure.png')
