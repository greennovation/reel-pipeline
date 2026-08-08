#!/usr/bin/env python3
"""ШАБЛОН оркестратора рилса. Скопируй как make_reel_<съёмка>.py.

Конвейер: тело (build+stitch) -> финал-литерал (имя + ПШШ) -> хоп (gen_finale)
-> грейд passthrough (gen_polish) -> музыка-пэд (gen_music) -> обложка (gen_cover).
Цвет НЕ трогаем — исходники уже SDR (Apple avconvert, см. PIPELINE §2).

Запуск: python3 make_reel_<съёмка>.py <reel_id>
"""
import subprocess, sys, tempfile, os
from pathlib import Path
from cut_reel import OUT_W, OUT_H
from stitch_reel import GRADE   # GRADE="null" passthrough (цвет уже правильный)
from стиль import кадров_в_секунду, загрузить_стиль

SHOOT = "TEMPLATE"
BUILD = f"build_{SHOOT}.py"          # твой build-файл
SDR_DIR = "raw_sdr"                  # папка SDR-исходников
STYLE = "Фирменный стиль.md"


def видеофильтр(стиль):
    fps = кадров_в_секунду(стиль)
    return f"{GRADE},scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase,crop={OUT_W}:{OUT_H},fps={fps}"

# Финал: id -> (видео_SDR, [(a,b)...]) — кусок «Меня зовут …, я Шипучка» + родной ПШШ.
# Пшш ищи по ZCR>0.4+энергия; нет в дубле — донор из др. файла той же съёмки.
FINALE = {
    # "myreel": ("raw_sdr/SHOT.mov", [(399.95, 402.30)]),
}


def run(c): subprocess.run(c, check=True)


def enc(args, out):
    run(["ffmpeg", "-y", "-v", "error", *args, "-c:v", "libx264", "-preset", "medium",
         "-crf", "19", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)])


def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return float(o.stdout.strip())


def main():
    rid = sys.argv[1]
    стиль = загрузить_стиль(STYLE)
    vf = видеофильтр(стиль)
    src, spans = FINALE[rid]
    run(["python3", BUILD, rid])
    run(["python3", "stitch_reel.py", f"plan/{SHOOT}_{rid}.json", STYLE])   # -> cut/<SHOOT>_<rid>.mp4
    tmp = Path(tempfile.mkdtemp(prefix=f"reel{rid}_"))
    body = f"cut/{SHOOT}_{rid}.mp4"; base = f"cut/{SHOOT}_{rid}_full.mp4"
    if spans:
        parts = []
        for i, (a, b) in enumerate(spans):
            p = tmp / f"fin{i}.mp4"; enc(["-ss", str(a), "-to", str(b), "-i", src, "-vf", vf], p); parts.append(p)
        lst = tmp / "concat.txt"
        lst.write_text("".join(f"file '{Path(p).resolve()}'\n" for p in [body, *parts]))
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", base])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", body, "-c", "copy", base])
    fin = f"cut/{SHOOT}_{rid}_final.mp4"; run(["python3", "gen_finale.py", base, fin, STYLE])
    pol = f"cut/{SHOOT}_{rid}_polished.mp4"; run(["python3", "gen_polish.py", fin, pol, f"{dur(fin)-3.0:.2f}"])
    pre = f"cut/{SHOOT}_{rid}_pre.mp4"; run(["python3", "gen_music.py", pol, pre, "0.05", "pad"])
    music = f"cut/{SHOOT}_{rid}_music.mp4"; run(["python3", "gen_cover.py", rid, pre, music])
    for f in [body, base, fin, pol, pre]:
        if os.path.exists(f): os.remove(f)
    print(f"OK -> {music}")


if __name__ == "__main__":
    main()
