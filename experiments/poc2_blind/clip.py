import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root
import numpy as np, os, time, random, subprocess
from PIL import Image
from fractadactyl.swap import *; from fractadactyl.color import colorize
A, B = load_worlds()
W, H, ss, FPS, SECS = 640, 360, 2, 30, 15
N = FPS*SECS
T = complex(-0.7436438870371587, 0.1318259042053120)
w0, w1 = 1e5, 3e-4
SWAP_F = 0.04                         # swap when patch spans 4% of width
w_swap = 2*PATCH_R / SWAP_F
ws = w0 * (w1/w0) ** (np.arange(N)/(N-1))
k_swap = int(np.argmax(ws <= w_swap))
fake_is = random.choice(["clip_1", "clip_2"])
real_is = "clip_2" if fake_is == "clip_1" else "clip_1"
open("answer.txt", "w").write(f"fake = {fake_is} (swap at frame {k_swap}, t = {k_swap/FPS:.2f}s)\n")
for d in ("clip_1", "clip_2"): os.makedirs(d, exist_ok=True)
ab = None; t0 = time.time()
for k, w in enumerate(ws):
    nA, dA = render_world(A, T, w, W, H, ss)
    real = colorize(nA, dA, freq=1.5)
    out = real
    if k >= k_swap:
        nB, dB = render_world(B, T, w, W, H, ss)
        mk = patch_mask(T, w, W, H)
        if ab is None: ab = fit_nu_map(nA.mean(2), nB.mean(2), mk)
        fake = colorize(apply_nu_map(nB, ab), dB, freq=1.5).astype(float)
        out = (real*(1-mk[..., None]) + fake*mk[..., None]).astype(np.uint8)
    Image.fromarray(real).save(f"{real_is}/f{k:04d}.png")
    Image.fromarray(out).save(f"{fake_is}/f{k:04d}.png")
    if k % 15 == 0:
        el = time.time()-t0
        print(f"frame {k}/{N}  elapsed {el/60:5.1f} min  eta {el/(k+1)*(N-k-1)/60:5.1f} min", flush=True)
for d in ("clip_1", "clip_2"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{d}/f%04d.png",
                    "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-crf", "14",
                    "-pix_fmt", "yuv420p", f"{d}.mp4"], check=True)
print("done", flush=True)
