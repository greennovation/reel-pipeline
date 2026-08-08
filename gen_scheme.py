#!/usr/bin/env python3
"""Панель-схема в нижней части кадра для обучающих рилсов.

Текст панели использует шрифт и цвета из раздела ``субтитры`` фирменного
стиля, поэтому схема остаётся частью того же оформления, что и субтитры.

Запуск: python3 gen_scheme.py <reel_id> <вход.mp4> <выход.mp4> [Фирменный стиль.md]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from стиль import УМОЛЧАНИЯ, загрузить_стиль, параметры_субтитров, путь_к_шрифту


_ВУАЛЬ = (10, 22, 15, 210)
_ТЁМНЫЙ_ТЕКСТ = (10, 22, 15)
APPEAR, TAIL = 2.5, 3.5  # старт после обложки; хвост (финал) без панели

# Схемы по роликам: заголовок + шаги (номер крупно, подпись)
SCHEMES = {
    "premium1": {"title": "от нуля до профи", "steps": [
        "Контекст — дай ИИ свой",
        "4D-тест — что отдать",
        "Свой маленький скилл",
        "Харнес — обвязка модели",
        "Система — личная ОС",
    ]},
    "premium2": {"title": "3 способа начать", "steps": [
        "Сложи заметки в одну папку",
        "Claude + data governance",
        "Семантика = меньше токенов",
    ]},
    "etl": {"title": "данные — это база", "steps": [
        "Extract — собрать данные",
        "Transform — преобразовать",
        "Load — выгрузить (Telegram)",
    ]},
}


def font(параметры, size, weight=None):
    f = ImageFont.truetype(str(путь_к_шрифту(параметры["шрифт"])), size)
    if weight:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def panel_png(rid, out, стиль=None):
    """Рендерит схему с текстовым оформлением из фирменного стиля."""
    параметры = параметры_субтитров(стиль or УМОЛЧАНИЯ)
    sch = SCHEMES[rid]
    steps = sch["steps"]
    width, height = параметры["ширина"], параметры["высота"]
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 40
    x0, x1 = pad, width - pad
    row_h, head_h = 104, 96
    panel_y = int(height * 0.609375)
    y1 = panel_y + head_h + len(steps) * row_h + 30
    active = параметры["цвет_активного_слова"]
    text = параметры["цвет_текста"]

    d.rounded_rectangle([x0, panel_y, x1, y1], 34, fill=_ВУАЛЬ, outline=active, width=3)
    title_font = font(параметры, round(параметры["размер"] * 4 / 3))
    tw = d.textlength(sch["title"], font=title_font)
    d.text(((width - tw) / 2, panel_y + 16), sch["title"], font=title_font, fill=active)

    number_font = font(параметры, параметры["размер"], 800)
    step_size = round(параметры["размер"] * 19 / 24)
    step_font = font(параметры, step_size, 600)
    sy = panel_y + head_h
    for i, step in enumerate(steps):
        cy = sy + i * row_h
        radius = 34
        cx = x0 + 56
        d.ellipse([cx - radius, cy + 8, cx + radius, cy + 8 + 2 * radius], fill=active)
        number = str(i + 1)
        nw = d.textlength(number, font=number_font)
        d.text((cx - nw / 2, cy + 12), number, font=number_font, fill=_ТЁМНЫЙ_ТЕКСТ)
        tx = cx + radius + 28
        available = x1 - tx - 24
        chosen_font = step_font
        for size in (step_size, round(step_size * 0.92), round(step_size * 0.84), round(step_size * 0.76)):
            chosen_font = font(параметры, size, 600)
            if d.textlength(step, font=chosen_font) <= available:
                break
        d.text((tx, cy + 18), step, font=chosen_font, fill=text)
        if i < len(steps) - 1:
            d.line([cx, cy + 8 + 2 * radius, cx, cy + row_h + 8], fill=active, width=4)
    img.save(out)


def main():
    rid, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    путь_стиля = sys.argv[4] if len(sys.argv) > 4 else "Фирменный стиль.md"
    стиль = загрузить_стиль(путь_стиля)
    tmp = Path(tempfile.mkdtemp(prefix="scheme_"))
    png = tmp / "panel.png"
    panel_png(rid, png, стиль)
    o = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", src],
        capture_output=True,
        text=True,
    )
    dur = float(o.stdout.strip())
    off = dur - TAIL
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src, "-loop", "1", "-t", str(dur), "-i", str(png),
         "-filter_complex",
         f"[1:v]format=rgba,fade=t=in:st={APPEAR}:d=0.4:alpha=1,fade=t=out:st={off - 0.4}:d=0.4:alpha=1[p];"
         f"[0:v][p]overlay=0:0:enable='between(t,{APPEAR},{off})'[v]",
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-c:a", "copy", dst],
        check=True,
    )
    print(f"OK схема {rid} -> {dst}")


if __name__ == "__main__":
    main()
