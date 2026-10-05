import numpy as np
def colorize(nu, de, lshift=0.0, freq=2.2):
    """hue from log(nu) (multiplicative iteration growth -> phase shift),
    brightness from pixel-normalized distance estimate (scale invariant)."""
    inside = nu < 0
    t = np.log(np.maximum(nu, 1.0)) * freq + lshift
    r = 0.5 + 0.5*np.cos(6.2832*(t + 0.00))
    g = 0.5 + 0.5*np.cos(6.2832*(t + 0.15))
    b = 0.5 + 0.5*np.cos(6.2832*(t + 0.35))
    rgb = np.stack([r, g, b], -1)
    shade = np.clip(np.tanh(de * 0.6), 0, 1)[..., None]   # dark lines at boundary
    rgb = rgb * shade
    rgb[inside] = 0
    rgb = rgb.mean(axis=2) if rgb.ndim == 4 else rgb      # average supersamples
    return (np.clip(rgb, 0, 1) ** (1/2.2) * 255).astype(np.uint8)
