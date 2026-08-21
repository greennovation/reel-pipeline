#!/usr/bin/env python3
"""Нарезка рилса и вшитые субтитры из «Фирменный стиль.md».

Оформление, включая положение, шрифт, цвета и способ отрисовки, задаётся
разделом ``субтитры`` фирменного стиля. Поддерживаются «тень» и «плашка».

Использование:
  python3 cut_reel.py --src raw/A001.mov --json transcripts/A001.json \
      --start 73.4 --end 98.1 --out cut/01_120skillov.mp4
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from стиль import УМОЛЧАНИЯ, загрузить_стиль, параметры_субтитров, путь_к_шрифту
import субтитры_нарезка


# Старые шаблоны импортируют размеры кадра из этого модуля. Их источник правды
# теперь тот же раздел «формат» в стиль.py, а рабочий рендер использует размеры
# конкретно загруженного фирменного стиля.
_РАЗМЕРЫ_УМОЛЧАНИЙ = параметры_субтитров(УМОЛЧАНИЯ)
OUT_W = _РАЗМЕРЫ_УМОЛЧАНИЙ["ширина"]
OUT_H = _РАЗМЕРЫ_УМОЛЧАНИЙ["высота"]


def подготовить_параметры_субтитров(стиль: dict[str, Any]) -> dict[str, Any]:
    """Выбирает и проверяет параметры субтитров из загруженного стиля."""
    return параметры_субтитров(стиль)


def _параметры_по_умолчанию() -> dict[str, Any]:
    """Возвращает встроенный стиль без чтения файла из текущего каталога."""
    return подготовить_параметры_субтитров(УМОЛЧАНИЯ)


def load_words(json_path, start, end):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    words = []
    for seg in data["segments"]:
        for w in seg.get("words", []):
            if w["start"] >= start - 0.05 and w["end"] <= end + 0.05:
                words.append(
                    {
                        "text": w["word"].strip(),
                        "start": w["start"] - start,
                        "end": w["end"] - start,
                    }
                )
    return words


def group_phrases(
    words,
    параметры: Optional[dict[str, Any]] = None,
    план: Optional[Sequence[int]] = None,
):
    """Бьёт слова на реплики: по смысловому плану помощника или по паузе и вместимости.

    ``план`` это номера слов, с которых начинается новая реплика. Его готовит
    помощник, читая расшифровку: название продукта целиком, предлог к своему слову,
    прилагательное с существительным. Плана нет, значит работает механика.
    """
    параметры = параметры or _параметры_по_умолчанию()
    return субтитры_нарезка.сгруппировать(
        words, параметры, шрифт=make_font(параметры, 600), план=план
    )


def wrap_lines(phrase, параметры: Optional[dict[str, Any]] = None):
    """Переносит слова по реальной ширине шрифта, а не по числу символов."""
    параметры = параметры or _параметры_по_умолчанию()
    return субтитры_нарезка.перенести(phrase, параметры, make_font(параметры, 600))


def make_font(параметры: dict[str, Any], weight: int):
    """Создаёт шрифт, выбранный в разделе ``субтитры``."""
    f = ImageFont.truetype(str(путь_к_шрифту(параметры["шрифт"])), параметры["размер"])
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def render_state(
    phrase,
    active_i,
    out_png,
    параметры: Optional[dict[str, Any]] = None,
):
    """Рендерит PNG с тенью, подсвечивая активное слово цветом стиля."""
    параметры = параметры or _параметры_по_умолчанию()
    img = Image.new("RGBA", (параметры["ширина"], параметры["высота"]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    шрифт = make_font(параметры, 600)
    lines = wrap_lines(phrase, параметры)
    shadow = Image.new("L", img.size, 0)
    ds = ImageDraw.Draw(shadow)
    for li, line in enumerate(lines):
        text = " ".join(w["text"] for w in line)
        total = d.textlength(text, font=шрифт)
        x = (параметры["ширина"] - total) / 2
        y = параметры["верх_блока"] + li * параметры["высота_строки"]
        ds.text((x + 7, y + 9), text, font=шрифт, fill=235)
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    img.paste(black, (0, 0), shadow)

    flat_idx = 0
    for li, line in enumerate(lines):
        text = " ".join(w["text"] for w in line)
        total = d.textlength(text, font=шрифт)
        x = (параметры["ширина"] - total) / 2
        y = параметры["верх_блока"] + li * параметры["высота_строки"]
        for w in line:
            fill = (
                параметры["цвет_активного_слова"]
                if flat_idx == active_i
                else параметры["цвет_текста"]
            )
            d.text((x, y), w["text"], font=шрифт, fill=fill)
            x += d.textlength(w["text"] + " ", font=шрифт)
            flat_idx += 1
    img.save(out_png)


def отрисовщик_субтитров(
    стиль: dict[str, Any],
) -> tuple[Callable[..., None], dict[str, Any]]:
    """Возвращает рендерер, явно выбранный ``субтитры.стиль``."""
    параметры = подготовить_параметры_субтитров(стиль)
    if параметры["стиль"] == "тень":
        return render_state, параметры
    if параметры["стиль"] == "плашка":
        from sub_plashka import render_state as отрисовать_плашку

        return отрисовать_плашку, параметры
    raise AssertionError("параметры_субтитров должен проверить стиль субтитров")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", default="Фирменный стиль.md")
    args = ap.parse_args()

    стиль = загрузить_стиль(args.style)
    render, параметры = отрисовщик_субтитров(стиль)
    words = load_words(args.json, args.start, args.end)
    if not words:
        raise SystemExit("В этом интервале нет слов — проверь таймкоды")
    phrases = group_phrases(words, параметры)

    tmp = Path(tempfile.mkdtemp(prefix="reel_"))
    overlays = []  # (png, start, end)
    for pi, phrase in enumerate(phrases):
        for wi, w in enumerate(phrase):
            png = tmp / f"p{pi:02d}_w{wi:02d}.png"
            render(phrase, wi, png, параметры)
            until = phrase[wi + 1]["start"] if wi + 1 < len(phrase) else phrase[-1]["end"] + 0.15
            overlays.append((png, w["start"], until))

    inputs = ["-ss", str(args.start), "-to", str(args.end), "-i", args.src]
    for png, _, _ in overlays:
        inputs += ["-i", str(png)]
    ширина, высота = параметры["ширина"], параметры["высота"]
    fc = [f"[0:v]scale={ширина}:{высота}:force_original_aspect_ratio=increase,crop={ширина}:{высота}[v0]"]
    prev = "v0"
    for i, (_, start, end) in enumerate(overlays):
        nxt = f"v{i + 1}"
        fc.append(f"[{prev}][{i + 1}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{nxt}]")
        prev = nxt
    cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
        "-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", args.out,
    ]
    subprocess.run(cmd, check=True)
    print(f"OK {args.out}: {len(phrases)} фраз, {len(overlays)} слов-состояний")


if __name__ == "__main__":
    main()
