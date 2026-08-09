"""Единая проверка минимальной версии ffmpeg для движка рилсов."""
from __future__ import annotations

import re
import sys


МИНИМАЛЬНАЯ_ВЕРСИЯ_FFMPEG = (4, 4)
_ШАБЛОН_ВЕРСИИ = re.compile(r"^ffmpeg version (\d+(?:\.\d+){1,2})\b", re.MULTILINE)


def текст_минимальной_версии() -> str:
    """Возвращает минимальную версию в формате, понятном автору рилса."""
    return ".".join(map(str, МИНИМАЛЬНАЯ_ВЕРСИЯ_FFMPEG))


def проверить_версию_ffmpeg(вывод: str) -> str:
    """Проверяет вывод ``ffmpeg -version`` и возвращает найденную версию."""
    совпадение = _ШАБЛОН_ВЕРСИИ.search(вывод)
    минимум = текст_минимальной_версии()
    if совпадение is None:
        raise ValueError(
            "Не удалось определить версию ffmpeg из вывода «ffmpeg -version». "
            f"Нужна версия не ниже {минимум}."
        )

    текст_версии = совпадение.group(1)
    версия = tuple(map(int, текст_версии.split(".")))
    if версия < МИНИМАЛЬНАЯ_ВЕРСИЯ_FFMPEG:
        raise ValueError(
            f"ffmpeg {текст_версии} слишком старый: нужна версия не ниже {минимум}."
        )
    return текст_версии


def main() -> int:
    """Проверяет вывод из stdin, чтобы pipeline_check.sh не дублировал порог."""
    try:
        print(проверить_версию_ffmpeg(sys.stdin.read()))
    except ValueError as ошибка:
        print(ошибка, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
