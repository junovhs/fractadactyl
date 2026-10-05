import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
import numpy as np
from fractadactyl import pert
from fractadactyl.color import colorize
from PIL import Image
p = 936
c0 = pert.nucleus_mp(complex(-0.743643901389397, 0.131825877436311), p)
Z, s = pert.reference(c0, p)
print("check Z periodic: |z_p| via orbit", abs(Z[-1]**2 + complex(c0)))
W, H = 240, 240
imgs = []
for w in [400.0, 40.0, 4.0]:
    b, db = pert.render(Z.real.copy(), Z.imag.copy(), 0.0, 0.0, w*abs(s), 0.0, W, H, 300*p, 1)
    print(w, "interior frac", (b<0).mean())
    imgs.append(colorize(b, db, freq=4))
Image.fromarray(np.concatenate(imgs, 1)).save('look3.png')
