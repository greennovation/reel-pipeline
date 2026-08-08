import importlib.util
import json
from pathlib import Path

import pytest

from ролик import загрузить_ролик, пути_ролика, прочитать_слова, собрать_план


def _записать_описание(tmp_path: Path, yaml_шапка: str) -> Path:
    путь = tmp_path / "ролик.md"
    путь.write_text(f"---\n{yaml_шапка}\n---\n# Заметки\n", encoding="utf-8")
    return путь


def _минимум(дополнение: str = "") -> str:
    return "ролик: тест\nисходник: IMG_0421.MOV\nкуски:\n  - [1.0, 2.0]\n" + дополнение


def test_фикстура_шаблона_рилса_читается():
    файл = Path(__file__).parent / "данные" / "_шаблон рилса.md"

    описание = загрузить_ролик(файл)

    assert описание["ролик"] == "пример_рилса"
    assert len(описание["куски"]) == 2


def test_разбирает_оба_вида_кусков_и_пустой_финал(tmp_path: Path):
    путь = _записать_описание(
        tmp_path,
        _минимум(
            "  - отрезок: [3.0, 4.0]\n    слова:\n      - [Ручной, 3.1, 3.3]\nбез_субтитров: []\n"
        ),
    )

    описание = загрузить_ролик(путь)

    assert описание["куски"][0] == [1.0, 2.0]
    assert описание["куски"][1]["слова"][0] == ["Ручной", 3.1, 3.3]
    assert описание["финал"]["исходник"] == "IMG_0421.MOV"
    assert описание["обложка"] == {"строка1": "", "строка2": "", "стикер": ""}


def test_пути_выводятся_по_соглашению(tmp_path: Path):
    описание = загрузить_ролик(_записать_описание(tmp_path, _минимум()))

    assert пути_ролика(описание, tmp_path) == {
        "исходник": tmp_path / "raw" / "IMG_0421.MOV",
        "приведённый_цвет": tmp_path / "raw_sdr" / "IMG_0421.mov",
        "транскрипт": tmp_path / "transcripts" / "IMG_0421.json",
    }


@pytest.mark.parametrize("поле", ["ролик", "исходник"])
def test_обязательное_поле_названо_в_ошибке(tmp_path: Path, поле: str):
    строки = {"ролик": "тест", "исходник": "IMG.MOV"}
    del строки[поле]
    yaml_шапка = "\n".join(f"{ключ}: {значение}" for ключ, значение in строки.items()) + "\nкуски: []\n"

    with pytest.raises(ValueError, match=поле):
        загрузить_ролик(_записать_описание(tmp_path, yaml_шапка))


def test_неверный_конец_куска_называет_поле_и_номер(tmp_path: Path):
    with pytest.raises(ValueError, match=r"куски.*кусок 2.*конец"):
        загрузить_ролик(_записать_описание(tmp_path, _минимум("  - [3, 3]\n")))


def test_наложение_кусков_называет_поле_и_номер(tmp_path: Path):
    with pytest.raises(ValueError, match=r"куски.*кусок 2.*налезает"):
        загрузить_ролик(
            _записать_описание(tmp_path, _минимум("  - [1.5, 3.0]\n"))
        )


def test_номер_без_субтитров_вне_границ_называет_поле_и_номер(tmp_path: Path):
    with pytest.raises(ValueError, match=r"без_субтитров.*кусок 1"):
        загрузить_ролик(_записать_описание(tmp_path, _минимум("без_субтитров: [1]\n")))


def test_прочитать_слова_склеивает_дефисный_хвост(tmp_path: Path):
    путь = tmp_path / "слова.json"
    путь.write_text(
        json.dumps(
            {"segments": [{"words": [
                {"word": "как", "start": 1.001, "end": 1.2},
                {"word": "-то", "start": 1.2, "end": 1.5},
            ]}]}
        ),
        encoding="utf-8",
    )

    assert прочитать_слова(путь) == [{"text": "как-то", "start": 1.0, "end": 1.5}]


def test_собрать_план_применяет_точечную_правку_до_общей(tmp_path: Path):
    описание = загрузить_ролик(
        _записать_описание(
            tmp_path,
            _минимум(
                "правки:\n  всегда:\n    Charge: ChatGPT\n  по_времени:\n    - [1.0, Charge, Точное]\n"
            ),
        )
    )
    слова = [
        {"text": "Charge", "start": 1.0, "end": 1.2},
        {"text": "Charge", "start": 1.3, "end": 1.5},
    ]

    план = собрать_план(описание, слова, {})

    assert [слово["text"] for слово in план["pieces"][0]["words"]] == ["Точное", "ChatGPT"]


def test_пустая_правка_убирает_слово_и_продлевает_предыдущее(tmp_path: Path):
    описание = загрузить_ролик(
        _записать_описание(tmp_path, _минимум("правки:\n  всегда:\n    убрать: ''\n"))
    )
    слова = [
        {"text": "оставить", "start": 1.0, "end": 1.2},
        {"text": "убрать", "start": 1.2, "end": 1.6},
    ]

    план = собрать_план(описание, слова, {})

    assert план["pieces"][0]["words"] == [{"text": "оставить", "start": 1.0, "end": 1.6}]


def test_досчёт_хвоста_куска_повторяет_шаблон(tmp_path: Path):
    описание = загрузить_ролик(
        _записать_описание(
            tmp_path,
            "ролик: тест\nисходник: IMG_0421.MOV\nкуски:\n  - [1.0, 1.6]\n",
        )
    )
    слова = [
        {"text": "первое", "start": 1.1, "end": 1.3},
        {"text": "последнее", "start": 1.5, "end": 1.7},
        {"text": "следующее", "start": 1.75, "end": 2.1},
    ]

    план = собрать_план(описание, слова, {})

    assert план["pieces"][0]["start"] == 1.0
    assert план["pieces"][0]["end"] == 1.73


def test_пустой_кусок_называет_номер(tmp_path: Path):
    описание = загрузить_ролик(_записать_описание(tmp_path, _минимум()))

    with pytest.raises(ValueError, match=r"Пустой кусок 1"):
        собрать_план(описание, [], {})


def test_план_совпадает_со_старым_шаблоном(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    шаблон = Path(__file__).parents[1] / "templates" / "build_TEMPLATE.py"
    spec = importlib.util.spec_from_file_location("старый_шаблон", шаблон)
    assert spec and spec.loader
    старый = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(старый)
    старый.SHOOT = "TEMPLATE"
    старый.SOURCES = {"совместимость": ("raw_sdr/IMG_0421.mov", "transcripts/IMG_0421.json")}
    старый.REELS = {"совместимость": [(1.0, 2.0)]}
    старый.NOSUB = {}
    старый.TIMED = {(1.0, "Charge"): "Точное"}
    старый.GLOBAL = {"Charge": "ChatGPT"}
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "transcripts" / "IMG_0421.json").write_text(
        json.dumps({"segments": [{"words": [
            {"word": "Charge", "start": 1.0, "end": 1.2},
            {"word": "Charge", "start": 1.3, "end": 1.5},
            {"word": "следующее", "start": 1.9, "end": 2.1},
        ]}]}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    старый.build("совместимость")
    ожидаемый = json.loads((tmp_path / "plan" / "TEMPLATE_совместимость.json").read_text())

    описание = загрузить_ролик(
        _записать_описание(
            tmp_path,
            "ролик: TEMPLATE_совместимость\nисходник: IMG_0421.MOV\nкуски:\n  - [1.0, 2.0]\n"
            "правки:\n  всегда:\n    Charge: ChatGPT\n  по_времени:\n    - [1.0, Charge, Точное]\n",
        )
    )
    полученный = собрать_план(описание, прочитать_слова(tmp_path / "transcripts" / "IMG_0421.json"), {})

    assert полученный == ожидаемый
