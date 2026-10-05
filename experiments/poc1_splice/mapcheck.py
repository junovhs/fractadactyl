import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
from fractadactyl.mb import *; from fractadactyl.color import colorize
from PIL import Image
seed = complex(-0.743643887037151, 0.131825904205330)
W, H = 480, 360
for p_try in (78, 936):
    c0 = nucleus(seed, p_try) if p_try==78 else complex(-0.743643901389397, 0.131825877436311)
    c0 = nucleus(c0, p_try)
    s = mini_size(c0, p_try)
    imgs = []; nus = []
    for (cen, w, rot, mi) in [(complex(-0.75,0), 3.0, 0.0, 2000),
                              (c0 + s*(-0.75), 3.0*abs(s), np.angle(s), 300*p_try)]:
        nu, de = render(cen.real, cen.imag, w, rot, W, H, mi, 2)
        nus.append(nu)
        imgs.append((nu, de))
    a, b = nus
    m = (a > 0) & (b > 0)
    A = np.polyfit(a[m], b[m], 1)
    agree = np.mean((a < 0) == (b < 0))
    print(f"p={p_try} |s|={abs(s):.3e} interior-agreement={agree*100:.2f}%  nu_mini ~ {A[0]:.2f}*nu_main + {A[1]:.1f}")
    shift = 2.2*np.log(A[0])
    im0 = colorize(*imgs[0], lshift=shift); im1 = colorize(*imgs[1])
    Image.fromarray(np.concatenate([im0, im1], 1)).save(f"mapcheck_p{p_try}.png")
