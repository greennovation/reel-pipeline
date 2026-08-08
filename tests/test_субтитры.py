from copy import deepcopy
from pathlib import Path

from PIL import Image
import pytest

import cut_reel
import gen_scheme
import sub_plashka
from стиль import УМОЛЧАНИЯ, загрузить_стиль, параметры_субтитров


def _стиль() -> dict:
    return deepcopy(УМОЛЧАНИЯ)


def test_позиция_субтитров_меняет_подготовленную_координату():
    сверху = _стиль()
    снизу = _стиль()
    сверху["субтитры"]["позиция"] = 0.16
    снизу["субтитры"]["позиция"] = 0.74

    верхняя_координата = параметры_субтитров(сверху)["верх_блока"]
    нижняя_координата = параметры_субтитров(снизу)["верх_блока"]

    assert верхняя_координата != нижняя_координата
    assert верхняя_координата < нижняя_координата


def test_цвет_активного_слова_доходит_до_отрисовки(tmp_path: Path):
    стиль = _стиль()
    стиль["субтитры"]["цвет_активного_слова"] = "#123456"
    параметры = параметры_субтитров(стиль)
    png = tmp_path / "субтитры.png"

    cut_reel.render_state(
        [{"text": "слово", "start": 0.0, "end": 0.5}],
        0,
        png,
        параметры,
    )

    with Image.open(png) as image:
        цвета = set(image.get_flattened_data())
    assert (*параметры["цвет_активного_слова"], 255) in цвета


def test_плашка_выбирает_другой_рендерер_чем_тень():
    тень = _стиль()
    плашка = _стиль()
    плашка["субтитры"]["стиль"] = "плашка"

    рендерер_тени, _ = cut_reel.отрисовщик_субтитров(тень)
    рендерер_плашки, _ = cut_reel.отрисовщик_субтитров(плашка)

    assert рендерер_тени is cut_reel.render_state
    assert рендерер_плашки is sub_plashka.render_state


def test_плашка_сохраняет_исторический_центр_и_свои_умолчания(tmp_path: Path):
    файл_стиля = tmp_path / "стиль.md"
    файл_стиля.write_text("```yaml\nсубтитры:\n  стиль: плашка\n```", encoding="utf-8")
    параметры = параметры_субтитров(загрузить_стиль(файл_стиля))
    png = tmp_path / "плашка.png"

    sub_plashka.render_state(
        [{"text": "слово", "start": 0.0, "end": 0.5}],
        0,
        png,
    )

    assert параметры["размер"] == 52
    assert параметры["высота_строки"] == 76
    assert параметры["символов_в_строке"] == 16
    with Image.open(png) as image:
        assert image.getbbox()[1] == int(1920 * 0.74) - 76 // 2 - 22


def test_схема_берёт_шрифт_и_цвета_субтитров(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    стиль = _стиль()
    стиль["субтитры"].update(
        {
            "шрифт": "Oswald.ttf",
            "цвет_текста": "#123456",
            "цвет_активного_слова": "#654321",
        }
    )
    png = tmp_path / "схема.png"
    шрифты = []
    исходный_шрифт = gen_scheme.font

    def запомнить_шрифт(параметры, размер, вес=None):
        шрифты.append(параметры["шрифт"])
        return исходный_шрифт(параметры, размер, вес)

    monkeypatch.setattr(gen_scheme, "font", запомнить_шрифт)
    gen_scheme.panel_png("premium2", png, стиль)

    with Image.open(png) as image:
        цвета = {значение[:3] for значение in image.get_flattened_data()}
    assert шрифты and set(шрифты) == {"Oswald.ttf"}
    assert параметры_субтитров(стиль)["цвет_текста"] in цвета
    assert параметры_субтитров(стиль)["цвет_активного_слова"] in цвета


def test_неизвестный_стиль_субтитров_называет_допустимые():
    стиль = _стиль()
    стиль["субтитры"]["стиль"] = "неон"

    with pytest.raises(ValueError, match=r"тень.*плашка"):
        cut_reel.отрисовщик_субтитров(стиль)
