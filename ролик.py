"""Описание рилса в Markdown и построение плана для ``stitch_reel.py``."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Iterable

import yaml


def _ошибка_куска(номер: int, текст: str) -> ValueError:
    return ValueError(f"Поле «куски», кусок {номер}: {текст}")


def _число(значение: Any) -> bool:
    return isinstance(значение, (int, float)) and not isinstance(значение, bool)


def _отрезок(кусок: Any, номер: int) -> tuple[float, float]:
    """Читает границы обычного или явного куска."""
    значение = кусок.get("отрезок") if isinstance(кусок, dict) else кусок
    if not isinstance(значение, (list, tuple)) or len(значение) != 2:
        raise _ошибка_куска(номер, "ожидается отрезок [начало, конец]")
    начало, конец = значение
    if not _число(начало) or not _число(конец):
        raise _ошибка_куска(номер, "границы отрезка должны быть числами")
    начало, конец = float(начало), float(конец)
    if конец <= начало:
        raise _ошибка_куска(номер, "конец должен быть больше начала")
    return начало, конец


def _проверить_куски(куски: Any) -> None:
    if not isinstance(куски, list):
        raise ValueError("Поле «куски» должно быть списком")
    отрезки = [(номер, *_отрезок(кусок, номер)) for номер, кусок in enumerate(куски, start=1)]
    for (_, _, конец_предыдущего), (номер, начало, _) in zip(
        sorted(отрезки, key=lambda отрезок: отрезок[1]),
        sorted(отрезки, key=lambda отрезок: отрезок[1])[1:],
    ):
        if начало < конец_предыдущего:
            raise _ошибка_куска(номер, "отрезок налезает на предыдущий кусок")


def _проверить_без_субтитров(номера: Any, количество_кусков: int) -> None:
    if not isinstance(номера, list):
        raise ValueError("Поле «без_субтитров» должно быть списком номеров кусков")
    for номер in номера:
        if not isinstance(номер, int) or isinstance(номер, bool) or not 0 <= номер < количество_кусков:
            raise ValueError(
                f"Поле «без_субтитров», кусок {номер}: номер выходит за границы списка кусков"
            )


def _шапка(текст: str, путь: Path) -> str:
    """Возвращает YAML-шапку, которая должна быть первым блоком файла."""
    совпадение = re.match(r"^\ufeff?[ \t]*---[ \t]*\r?\n(.*?)(?:\r?\n)?---[ \t]*(?:\r?\n|$)", текст, re.DOTALL)
    if not совпадение:
        raise ValueError(f"В файле «{путь}» не найдена YAML-шапка между строками ---")
    return совпадение.group(1)


def _проверить_описание(описание: dict[str, Any]) -> None:
    for поле in ("ролик", "исходник"):
        if not описание.get(поле):
            raise ValueError(f"Обязательное поле «{поле}» не заполнено")
    _проверить_куски(описание["куски"])
    _проверить_без_субтитров(описание["без_субтитров"], len(описание["куски"]))


def загрузить_ролик(путь: str | Path) -> dict[str, Any]:
    """Читает YAML-шапку Markdown и проверяет описание рилса.

    Необязательные разделы возвращаются с пустыми значениями, чтобы движок не
    заставлял автора Markdown перечислять технические пустышки.
    """
    файл = Path(путь)
    try:
        текст = файл.read_text(encoding="utf-8")
    except FileNotFoundError as ошибка:
        raise ValueError(f"Не найден файл описания рилса «{файл}»") from ошибка
    блок = _шапка(текст, файл)
    try:
        описание = yaml.safe_load(блок) or {}
    except yaml.YAMLError as ошибка:
        метка = getattr(ошибка, "problem_mark", None)
        строка = метка.line + 1 if метка is not None else "неизвестна"
        причина = getattr(ошибка, "problem", str(ошибка))
        raise ValueError(
            f"Не удалось прочитать YAML-шапку в файле «{файл}», строка {строка}: {причина}"
        ) from ошибка
    if not isinstance(описание, dict):
        raise ValueError(f"YAML-шапка в файле «{файл}» должна содержать словарь")

    описание = deepcopy(описание)
    описание.setdefault("куски", [])
    описание.setdefault("без_субтитров", [])
    правки = описание.setdefault("правки", {})
    if not isinstance(правки, dict):
        raise ValueError("Поле «правки» должно быть словарём")
    правки.setdefault("всегда", {})
    правки.setdefault("по_времени", [])
    финал = описание.setdefault("финал", {})
    if not isinstance(финал, dict):
        raise ValueError("Поле «финал» должно быть словарём")
    финал.setdefault("исходник", "")
    финал.setdefault("куски", [])
    if not финал["исходник"]:
        финал["исходник"] = описание.get("исходник")
    обложка = описание.setdefault("обложка", {})
    if not isinstance(обложка, dict):
        raise ValueError("Поле «обложка» должно быть словарём")
    for поле in ("строка1", "строка2", "стикер"):
        обложка.setdefault(поле, "")

    _проверить_описание(описание)
    return описание


def пути_ролика(описание: dict[str, Any], корень: str | Path) -> dict[str, Path]:
    """Выводит пути исходника, SDR-копии и транскрипта по имени исходника.

    Ключи результата: ``исходник`` (``raw``), ``приведённый_цвет``
    (``raw_sdr``) и ``транскрипт`` (``transcripts``).
    """
    if not описание.get("исходник"):
        raise ValueError("Обязательное поле «исходник» не заполнено")
    имя = Path(str(описание["исходник"]))
    база = Path(корень)
    return {
        "исходник": база / "raw" / имя,
        "приведённый_цвет": база / "raw_sdr" / имя.with_suffix(".mov"),
        "транскрипт": база / "transcripts" / имя.with_suffix(".json"),
    }


def прочитать_слова(путь_json: str | Path) -> list[dict[str, Any]]:
    """Читает слова Whisper и склеивает дефисные хвосты, как старый шаблон."""
    данные = json.loads(Path(путь_json).read_text(encoding="utf-8"))
    сырые: list[dict[str, Any]] = []
    for сегмент in данные["segments"]:
        for слово in сегмент.get("words", []):
            сырые.append(
                {
                    "text": str(слово["word"]).strip(),
                    "start": round(float(слово["start"]), 2),
                    "end": round(float(слово["end"]), 2),
                }
            )

    слова: list[dict[str, Any]] = []
    for слово in сырые:
        if слово["text"].startswith("-") and слова:
            слова[-1]["text"] += слово["text"]
            слова[-1]["end"] = слово["end"]
        else:
            слова.append(dict(слово))
    return слова


_ВРЕМЯ_СЛОВО = re.compile(r"^\s*\(?\s*([+-]?\d+(?:\.\d+)?)\s*[,|:]\s*(.*?)\s*\)?\s*$")


def _точечная_правка(правки: Any, начало: float, текст: str) -> Any | None:
    """Поддерживает краткую YAML-запись списка и читаемые записи-словари."""
    if isinstance(правки, dict):
        for ключ, замена in правки.items():
            if isinstance(ключ, tuple) and len(ключ) == 2:
                время, слово = ключ
                if float(время) == начало and слово == текст:
                    return замена
            if _число(ключ) and isinstance(замена, dict) and float(ключ) == начало:
                if текст in замена:
                    return замена[текст]
            if isinstance(ключ, str):
                совпадение = _ВРЕМЯ_СЛОВО.match(ключ)
                if совпадение and float(совпадение.group(1)) == начало and совпадение.group(2) == текст:
                    return замена
        return None

    if not isinstance(правки, list):
        return None
    for запись in правки:
        if isinstance(запись, (list, tuple)) and len(запись) == 3:
            время, слово, замена = запись
        elif isinstance(запись, dict):
            время = запись.get("время", запись.get("начало"))
            слово = запись.get("слово")
            замена = запись.get("замена", запись.get("текст", запись.get("на")))
        else:
            continue
        if _число(время) and float(время) == начало and слово == текст:
            return замена
    return None


def _исправить_слово(слово: dict[str, Any], правки: dict[str, Any]) -> Any:
    по_времени = _точечная_правка(правки.get("по_времени", []), слово["start"], слово["text"])
    if по_времени is not None:
        return по_времени
    всегда = правки.get("всегда", {})
    return всегда.get(слово["text"], слово["text"]) if isinstance(всегда, dict) else слово["text"]


def _слова_явного_куска(кусок: dict[str, Any], номер: int) -> Iterable[dict[str, Any]]:
    if "слова" not in кусок:
        raise _ошибка_куска(номер, "для явного куска нужно поле «слова»")
    слова = кусок["слова"]
    if not isinstance(слова, list):
        raise _ошибка_куска(номер, "поле «слова» должно быть списком")
    for слово in слова:
        if isinstance(слово, dict):
            текст, начало, конец = слово.get("text"), слово.get("start"), слово.get("end")
        elif isinstance(слово, (list, tuple)) and len(слово) == 3:
            текст, начало, конец = слово
        else:
            raise _ошибка_куска(номер, "слово должно иметь вид [текст, начало, конец]")
        if not isinstance(текст, str) or not _число(начало) or not _число(конец):
            raise _ошибка_куска(номер, "у слова нужны текст, начало и конец")
        yield {"text": текст, "start": float(начало), "end": float(конец)}


def _применить_правки(
    слова: Iterable[dict[str, Any]], правки: dict[str, Any]
) -> list[dict[str, Any]]:
    результат: list[dict[str, Any]] = []
    for слово in слова:
        текст = _исправить_слово(слово, правки)
        if текст == "":
            if результат:
                результат[-1]["end"] = слово["end"]
            continue
        результат.append({"text": текст, "start": слово["start"], "end": слово["end"]})
    return результат


def собрать_план(описание: dict[str, Any], слова: list[dict[str, Any]]) -> dict[str, Any]:
    """Собирает JSON-совместимый со ``stitch_reel.py`` план нарезки.

    План содержит только монтажные таймкоды и слова. Оформление субтитров не
    влияет на него по существу: ``stitch_reel.py`` читает фирменный стиль при
    отрисовке, поэтому параметр стиля здесь намеренно отсутствует.
    """
    _проверить_описание(описание)
    правки = описание.get("правки", {})
    if not isinstance(правки, dict):
        raise ValueError("Поле «правки» должно быть словарём")
    без_субтитров = set(описание.get("без_субтитров", []))
    куски_плана: list[dict[str, Any]] = []

    for индекс, кусок in enumerate(описание["куски"]):
        номер = индекс + 1
        начало, конец = _отрезок(кусок, номер)
        явный = isinstance(кусок, dict)
        if явный:
            исходные_слова = list(_слова_явного_куска(кусок, номер))
        else:
            исходные_слова = [
                dict(слово)
                for слово in слова
                if начало - 0.03 <= слово["start"] <= конец - 0.10
            ]
        слова_куска = _применить_правки(исходные_слова, правки)
        if not слова_куска:
            raise ValueError(f"Пустой кусок {номер}: после отбора и правок нет слов")

        if явный:
            старт_плана, конец_плана = начало, конец
        else:
            следующее = next(
                (
                    слово["start"]
                    for слово in слова
                    if слово["start"] > слова_куска[-1]["start"] + 0.01
                ),
                None,
            )
            конец_последнего = min(
                слова_куска[-1]["end"], слова_куска[-1]["start"] + 1.4
            )
            конец_плана = max(конец, конец_последнего + 0.12)
            if следующее is not None:
                конец_плана = min(конец_плана, следующее - 0.02)
            конец_плана = max(конец_плана, конец_последнего)
            старт_плана = min(начало, слова_куска[0]["start"] - 0.05)

        куски_плана.append(
            {
                "start": round(старт_плана, 2),
                "end": round(конец_плана, 2),
                "words": [] if индекс in без_субтитров else слова_куска,
            }
        )

    пути = пути_ролика(описание, Path("."))
    return {
        "src": str(пути["приведённый_цвет"]),
        "out": f"cut/{описание['ролик']}.mp4",
        "pieces": куски_плана,
    }
