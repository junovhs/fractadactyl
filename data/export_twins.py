"""One-time export of the Python twin library (data/twins.npz) to data/twins.json for the
Rust engine (DEC-05). Reference orbits are recomputed in Rust from the nucleus strings."""
import json, sys
import numpy as np

src = sys.argv[1] if len(sys.argv) > 1 else "data/twins.npz"
out = sys.argv[2] if len(sys.argv) > 2 else "data/twins.json"
with np.load(src) as f:
    d = {k: f[k] for k in f.files}
lib = [dict(p=int(d["p"][i]), s=[float(d["s"][i].real), float(d["s"][i].imag)], c0=str(d["c0"][i]),
            valid=float(d["valid"][i]), sig=[float(x) for x in d["sig"][i].astype(np.float32)])
       for i in range(len(d["p"]))]
json.dump(lib, open(out, "w"))
print(f"wrote {out}: {len(lib)} twins")
