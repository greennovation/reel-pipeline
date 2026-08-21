#!/usr/bin/env python3
"""Генератор 3D-LUT HLG (BT.2020) -> SDR (BT.709). Параметр SCALE = яркость.
Запуск: python3 gen_lut.py <scale> <out.cube>   (33^3)
"""
import sys, numpy as np
N = 33
SCALE = float(sys.argv[1]); OUT = sys.argv[2]

a, b, c = 0.17883277, 0.28466892, 0.55991073
def hlg_inv(Ep):                       # HLG signal -> scene linear
    return np.where(Ep <= 0.5, (Ep**2)/3.0, (np.exp((Ep - c)/a) + b)/12.0)

M = np.array([[1.6605, -0.5876, -0.0728],   # BT.2020 -> BT.709 (linear)
              [-0.1246, 1.1329, -0.0083],
              [-0.0182, -0.1006, 1.1187]])

def oetf709(L):
    L = np.clip(L, 0, 1)
    return np.where(L < 0.018, L*4.5, 1.099*np.power(L, 0.45) - 0.099)

lines = [f"LUT_3D_SIZE {N}"]
for bi in range(N):
    for gi in range(N):
        for ri in range(N):
            rgb = np.array([ri, gi, bi], float)/(N-1)
            lin = hlg_inv(rgb)
            lin = np.power(lin, 1.05)        # OOTF approx
            lin = M @ lin
            lin = lin * SCALE
            o = oetf709(lin)
            lines.append(f"{o[0]:.6f} {o[1]:.6f} {o[2]:.6f}")
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"OK {OUT} SCALE={SCALE}")
