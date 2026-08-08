#!/usr/bin/env python3
"""Рендерер субтитров «плашка» из фирменного стиля.

Шрифт, положение, перенос строк и оба цвета берутся из раздела
``субтитры``. Тёмная скруглённая подложка отличает этот рендерер от «тени».
"""
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from стиль import параметры_субтитров, путь_к_шрифту, стиль_с_умолчаниями_субтитров


_ЦВЕТ_ПЛАШКИ = (38, 38, 40, 150)
_ОТСТУП_ПО_ГОРИЗОНТАЛИ = 38
_ОТСТУП_ПО_ВЕРТИКАЛИ = 22
_РАДИУС_СКРУГЛЕНИЯ = 28


def _параметры_по_умолчанию() -> dict[str, Any]:
    """Возвращает встроенный стиль без чтения файла из текущего каталога."""
    return параметры_субтитров(стиль_с_умолчаниями_субтитров("плашка"))


def _font(параметры: dict[str, Any], weight: int = 700):
    f = ImageFont.truetype(str(путь_к_шрифту(параметры["шрифт"])), параметры["размер"])
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def wrap(words, параметры: dict[str, Any] | None = None):
    """Переносит текст по ширине строки из фирменного стиля."""
    параметры = параметры or _параметры_по_умолчанию()
    lines, line = [], []
    for w in words:
        if line and len(" ".join(x["text"] for x in line + [w])) > параметры["символов_в_строке"]:
            lines.append(line)
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(line)
    return lines


def render_state(
    phrase,
    active_i,
    out_png,
    параметры: dict[str, Any] | None = None,
):
    """Рендерит PNG с плашкой и подсветкой активного слова из стиля."""
    параметры = параметры or _параметры_по_умолчанию()
    img = Image.new("RGBA", (параметры["ширина"], параметры["высота"]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    шрифт = _font(параметры)
    lines = wrap(phrase, параметры)
    block_h = len(lines) * параметры["высота_строки"]
    y0 = параметры["центр_блока"] - block_h // 2

    widths = [d.textlength(" ".join(w["text"] for w in line), font=шрифт) for line in lines]
    plate_w = max(widths) + _ОТСТУП_ПО_ГОРИЗОНТАЛИ * 2
    px0 = (параметры["ширина"] - plate_w) / 2
    py0 = y0 - _ОТСТУП_ПО_ВЕРТИКАЛИ
    py1 = y0 + block_h + _ОТСТУП_ПО_ВЕРТИКАЛИ - (параметры["высота_строки"] - параметры["размер"])
    plate = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        [px0, py0, px0 + plate_w, py1],
        _РАДИУС_СКРУГЛЕНИЯ,
        fill=_ЦВЕТ_ПЛАШКИ,
    )
    img.alpha_composite(plate)

    flat = 0
    for li, line in enumerate(lines):
        text = " ".join(w["text"] for w in line)
        tw = d.textlength(text, font=шрифт)
        x = (параметры["ширина"] - tw) / 2
        y = y0 + li * параметры["высота_строки"]
        for w in line:
            fill = (
                параметры["цвет_активного_слова"]
                if flat == active_i
                else параметры["цвет_текста"]
            )
            d.text((x, y), w["text"], font=шрифт, fill=fill)
            x += d.textlength(w["text"] + " ", font=шрифт)
            flat += 1
    img.save(out_png)
