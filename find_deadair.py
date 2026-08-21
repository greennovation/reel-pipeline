#!/usr/bin/env python3
"""RMS-скан готового рилса → диапазоны пауз (молчание/отворот). Пишет plan/<name>_deadair.json.
Фон-шум держит уровень выше silencedetect, поэтому ищем ПРОВАЛЫ энергии.
Запуск: python3 find_deadair.py cut/NN_styled.mp4 cut/NN_final.mp4 [min_sec]
"""
import sys, subprocess, json, wave, array, tempfile
from pathlib import Path

inp, out = sys.argv[1], sys.argv[2]
mins = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8  # только ДЛИННЫЕ паузы (молчание/отворот)
INTRO_GUARD, OUTRO_GUARD = 0.7, 0.5  # не резать хук/заголовок и пшшш
wav = tempfile.mktemp(suffix=".wav")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", inp, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav, "rb"); sr = w.getframerate()
a = array.array("h"); a.frombytes(w.readframes(w.getnframes()))
win, hop = int(0.08 * sr), int(0.04 * sr)
env = [(i / sr, (sum(x * x for x in a[i:i + win]) / win) ** 0.5) for i in range(0, len(a) - win, hop)]
total = len(a) / sr
vals = sorted(r for _, r in env); thr = vals[len(vals) // 2] * 0.30
cuts, st = [], None
for t, r in env:
    if r < thr:
        if st is None: st = t
    else:
        if st is not None and t - st >= mins:
            cs, ce = round(st + 0.06, 2), round(t - 0.04, 2)
            if cs >= INTRO_GUARD and ce <= total - OUTRO_GUARD:  # беречь начало/конец
                cuts.append([cs, ce])
        st = None
name = Path(inp).stem.replace("_styled", "")
spec = {"in": inp, "out": out, "cuts": cuts}
Path(f"plan/{name}_deadair.json").write_text(
    json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8"
)
print(f"{name}: пауз {len(cuts)} →", cuts)
