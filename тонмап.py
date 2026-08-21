"""Приведение цвета iPhone HDR (HLG) к SDR: два взаимозаменяемых способа.

На macOS эталонный способ «apple» повторяет нативный тонмап Apple
`avconvert` (тот же цвет, что даёт iPhone/QuickTime) — команда и порядок
аргументов сохранены байт-в-байт с прежним вызовом в ``собрать_рилс.py``.

На Windows/Linux, где `avconvert` недоступен, используется способ «ffmpeg»:
HLG → BT.709 через `zscale` + `tonemap`. Цвет очень близок к яблочному, но
не идентичен ему — предупреждение об этом выведено в README.md и PIPELINE.md.

Выбор способа и запуск внешних команд принимают необязательный параметр
``запустить`` (по умолчанию — прямой ``subprocess.run``), чтобы вызывающий
код (``собрать_рилс.py``) мог подставить свою обёртку с едиными сообщениями
об отсутствующих инструментах, а тесты — подменить обе стадии моком.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

# Тип функции запуска внешней команды: список аргументов -> CompletedProcess.
Запустить = Callable[..., "subprocess.CompletedProcess[str]"]

СПОСОБ_APPLE = "apple"
СПОСОБ_FFMPEG = "ffmpeg"

# HLG (Hybrid Log-Gamma) и PQ (Perceptual Quantizer) — два HDR-transfer,
# которыми снимает iPhone и другие HDR-камеры. Всё остальное — SDR.
_HDR_TRANSFER = {"arib-std-b67", "smpte2084"}

# Тонмап HLG(BT.2020) -> BT.709: перевод в линейный свет, смена primaries,
# hable-тонмап без насыщения (desat=0, чтобы не тускнели цвета кожи), возврат
# в BT.709 OETF и стандартный 8-битный формат под последующий libx264.
_ФИЛЬТР_ТОНМАПА = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
)


class ОшибкаТонмапа(Exception):
    """Ошибка выбора или запуска способа приведения цвета к SDR."""


def _запустить_по_умолчанию(команда: Sequence[str], **kwargs: Any) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(list(команда), check=True, **kwargs)


def _есть_avconvert() -> bool:
    """Проверяет наличие Apple avconvert в PATH — так же, как это делает shell."""
    return shutil.which("avconvert") is not None


def _ffmpeg_умеет_zscale(запустить: Запустить) -> bool:
    """Проверяет, собран ли доступный ffmpeg с фильтром zscale (libzimg)."""
    try:
        результат = запустить(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (FileNotFoundError, ОшибкаТонмапа):
        return False
    except subprocess.CalledProcessError:
        return False
    вывод = результат.stdout or ""
    return re.search(r"\bzscale\b", вывод) is not None


def выбрать_способ(*, запустить: Запустить | None = None) -> str:
    """Выбирает способ приведения цвета: «apple» — эталон, «ffmpeg» — запасной."""
    if _есть_avconvert():
        return СПОСОБ_APPLE
    if _ffmpeg_умеет_zscale(запустить or _запустить_по_умолчанию):
        return СПОСОБ_FFMPEG
    raise ОшибкаТонмапа(
        "Не найден ни avconvert (только macOS), ни ffmpeg с фильтром zscale — "
        "приводить цвет HDR-съёмки iPhone к SDR нечем.\n"
        "Установите ffmpeg со сборкой, включающей zscale (libzimg):\n"
        "  Windows: choco install ffmpeg-full\n"
        "  Linux:   сборка пакетного менеджера с --enable-libzimg "
        "(например ffmpeg из deb-multimedia или собственная сборка)\n"
        "  macOS:   brew install ffmpeg, либо используйте системный avconvert"
    )


def определить_hdr(вход: Path, *, запустить: Запустить | None = None) -> bool:
    """Читает через ffprobe color_transfer потока и решает, HDR это или SDR."""
    запустить = запустить or _запустить_по_умолчанию
    результат = запустить(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=color_transfer",
            "-of",
            "default=nw=1:nk=1",
            str(вход),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    трансфер = (результат.stdout or "").strip().lower()
    return трансфер in _HDR_TRANSFER


def _apple_avconvert(вход: Path, выход: Path, *, запустить: Запустить) -> None:
    """Тот же вызов avconvert, что был в собрать_рилс.py, байт-в-байт."""
    запустить(
        [
            "avconvert",
            "-p",
            "Preset1920x1080",
            "-s",
            str(вход),
            "-o",
            str(выход),
            "--replace",
        ]
    )


def _ffmpeg_tonemap(вход: Path, выход: Path, *, запустить: Запустить) -> None:
    """HDR -> SDR через zscale+tonemap; SDR-вход проходит без тонмапа."""
    if определить_hdr(вход, запустить=запустить):
        фильтр = _ФИЛЬТР_ТОНМАПА
    else:
        фильтр = "format=yuv420p"
    запустить(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(вход),
            "-vf",
            фильтр,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "16",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-c:a",
            "copy",
            str(выход),
        ]
    )


def привести_к_sdr(
    вход: Path, выход: Path, способ: str, *, запустить: Запустить | None = None
) -> None:
    """Создаёт SDR-копию исходника выбранным способом."""
    запустить = запустить or _запустить_по_умолчанию
    if способ == СПОСОБ_APPLE:
        _apple_avconvert(вход, выход, запустить=запустить)
    elif способ == СПОСОБ_FFMPEG:
        _ffmpeg_tonemap(вход, выход, запустить=запустить)
    else:
        raise ОшибкаТонмапа(f"Неизвестный способ приведения цвета: «{способ}».")


def main(аргументы: Sequence[str] | None = None) -> int:
    """CLI для ручной проверки: python3 тонмап.py вход.MOV выход.mov"""
    аргументы = list(sys.argv[1:] if аргументы is None else аргументы)
    if len(аргументы) != 2:
        print("Использование: python3 тонмап.py <вход> <выход>", file=sys.stderr)
        return 2
    вход, выход = Path(аргументы[0]), Path(аргументы[1])
    try:
        способ = выбрать_способ()
        print(f"Способ: {способ}")
        привести_к_sdr(вход, выход, способ)
    except ОшибкаТонмапа as ошибка:
        print(f"Ошибка: {ошибка}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as ошибка:
        команда = " ".join(str(часть) for часть in ошибка.cmd)
        print(f"Ошибка: не удалось выполнить команду: {команда}", file=sys.stderr)
        return 1
    print(f"Готово: {выход}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
