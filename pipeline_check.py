#!/usr/bin/env python3
"""Проверка окружения для reel-пайплайна — кроссплатформенная версия.

Делает те же проверки, что и pipeline_check.sh, но работает и на Windows
(bash-скрипт там не запустить без WSL/Git Bash). Запуск:
    python3 pipeline_check.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent
sys.path.insert(0, str(КОРЕНЬ))

from ffmpeg_version import проверить_версию_ffmpeg  # noqa: E402
import тонмап  # noqa: E402

ОШИБКА_БЫЛА = False


def ok(строка: str) -> None:
    print(f"  ✅ {строка}")


def no(строка: str, подсказка: str) -> None:
    global ОШИБКА_БЫЛА
    ОШИБКА_БЫЛА = True
    print(f"  ❌ {строка} — {подсказка}")


def _запустить(команда: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        команда, capture_output=True, text=True, encoding="utf-8", check=False
    )


def проверить_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        no("ffmpeg", "Windows: choco install ffmpeg-full · macOS: brew install ffmpeg")
        return
    результат = _запустить(["ffmpeg", "-version"])
    try:
        версия = проверить_версию_ffmpeg(результат.stdout or "")
    except ValueError as ошибка:
        no("ffmpeg", str(ошибка))
        return
    ok(f"ffmpeg {версия}")


def проверить_ffprobe() -> None:
    if shutil.which("ffprobe") is None:
        no("ffprobe", "идёт вместе с ffmpeg")
        return
    ok("ffprobe")


def проверить_whisper() -> None:
    if shutil.which("whisper") is None:
        no("whisper", "python3 -m pip install -U openai-whisper")
        return
    ok("whisper (openai)")


def проверить_тонмап() -> None:
    try:
        способ = тонмап.выбрать_способ(запустить=_запустить)
    except тонмап.ОшибкаТонмапа as ошибка:
        no("цвет HDR→SDR", str(ошибка))
        return
    if способ == тонмап.СПОСОБ_APPLE:
        ok("цвет HDR→SDR: avconvert (эталон Apple)")
    else:
        ok("цвет HDR→SDR: ffmpeg zscale+tonemap (Windows/Linux)")


def проверить_python_пакет(имя: str, подсказка: str, показать_как: str | None = None) -> None:
    try:
        __import__(имя)
    except ImportError:
        no(показать_как or имя, подсказка)
        return
    ok(показать_как or имя)


def проверить_ассеты() -> None:
    шрифт = КОРЕНЬ / "assets" / "fonts" / "Unbounded.ttf"
    if шрифт.is_file():
        ok("шрифт Unbounded")
    else:
        no("Unbounded.ttf", "положи в assets/fonts/")

    стикеры = КОРЕНЬ / "assets" / "stickers"
    if стикеры.is_dir():
        количество = len(list(стикеры.glob("*.png")))
        ok(f"стикеры ({количество} шт)")
    else:
        no("assets/stickers/", "маскоты для обложек")


def проверить_папки() -> None:
    for имя in ("raw", "transcripts", "plan", "cut"):
        папка = КОРЕНЬ / имя
        if папка.is_dir():
            ok(f"{имя}/")
        else:
            папка.mkdir(parents=True, exist_ok=True)
            ok(f"{имя}/ (создана)")


def main() -> int:
    print("== Инструменты ==")
    проверить_ffmpeg()
    проверить_ffprobe()
    проверить_whisper()
    проверить_тонмап()
    проверить_python_пакет("PIL", "pip install pillow", показать_как="Pillow (субтитры)")
    проверить_python_пакет("numpy", "pip install numpy")
    print("== Ассеты ==")
    проверить_ассеты()
    print("== Папки ==")
    проверить_папки()
    print()
    if ОШИБКА_БЫЛА:
        print("⚠️  Есть пропуски — см. выше.")
        return 1
    print("✅ Окружение готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
