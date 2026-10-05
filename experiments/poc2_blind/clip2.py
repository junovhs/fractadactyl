import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
import numpy as np, os, time, random, subprocess, pickle
from PIL import Image
from fractadactyl import pert, minis
from fractadactyl.swap import SEED, PATCH_R, render_world, apply_nu_map
from fractadactyl.twins import soft_mask
from fractadactyl.color import colorize

scored = pickle.load(open(pathlib.Path(__file__).resolve().parents[2] / "data" / "poc2_twins.pkl", "rb"))
err, info, ab = scored[0]
A = minis.find(SEED, 1e-3)
c0 = pert.nucleus_mp(complex(info['c0'].replace(' ', '').strip('()')), info['p'])
Z, s = pert.reference(c0, info['p'])
B = dict(p=info['p'], s=s, Z=Z)
print(f"A p={A['p']} |s|={abs(A['s']):.2e};  twin B p={B['p']} |s|={abs(s):.2e} mismatch score {err:.2f}%", flush=True)

W, H, ss, FPS = 640, 360, 2, 30
T = complex(-0.7436438870371587, 0.1318259042053120)
w0, w1, NFULL = 1e5, 3e-4, 450            # identical camera path to test 1
ws_all = w0 * (w1/w0) ** (np.arange(NFULL)/(NFULL-1))
SWAP_F, FADE = 0.012, 10
k_swap = int(np.argmax(ws_all <= 2*PATCH_R/SWAP_F))
N = k_swap + FADE + 90
ws = ws_all[:N]
fake_is = random.choice(["A", "B"]); real_is = "B" if fake_is == "A" else "A"
open("answer2.txt", "w").write(f"fake = {fake_is}  (fade starts frame {k_swap}, fully swapped by frame {k_swap+FADE-1})\n")
for d in ("A", "B"): os.makedirs(f"frames_{d}", exist_ok=True)
t0 = time.time()
for k, w in enumerate(ws):
    nA, dA = render_world(A, T, w, W, H, ss)
    real = colorize(nA, dA, freq=1.5)
    out = real
    if k >= k_swap:
        alpha = min(1.0, (k - k_swap + 1) / FADE)
        alpha = alpha*alpha*(3 - 2*alpha)
        nB, dB = render_world(B, T, w, W, H, ss)
        mk = soft_mask(T, w, W, H) * alpha
        fake = colorize(apply_nu_map(nB, ab), dB, freq=1.5).astype(float)
        out = (real*(1-mk[..., None]) + fake*mk[..., None]).astype(np.uint8)
    Image.fromarray(real).save(f"frames_{real_is}/f{k:04d}.png")
    Image.fromarray(out).save(f"frames_{fake_is}/f{k:04d}.png")
    if k % 15 == 0:
        print(f"frame {k}/{N}  elapsed {(time.time()-t0)/60:5.1f} min", flush=True)
os.makedirs("blindtest2", exist_ok=True)
for d in ("A", "B"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"frames_{d}/f%04d.png",
                    "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p",
                    f"blindtest2/{d}.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"blindtest2/{d}.mp4", "-vf",
                    r"drawtext=fontfile='C\:/Windows/Fonts/arial.ttf':text='frame %{n}':x=20:y=20:fontsize=36:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=8",
                    "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", f"blindtest2/{d}_frames.mp4"], check=True)
print("done", flush=True)
