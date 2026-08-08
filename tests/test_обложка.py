from pathlib import Path

from PIL import Image

import gen_cover


КОРЕНЬ = Path(__file__).parents[1]


def _записать_ролик(tmp_path: Path, стикер: str) -> Path:
    путь = tmp_path / "ролик.md"
    путь.write_text(
        "---\n"
        "ролик: тест\n"
        "исходник: IMG_0421.MOV\n"
        "куски:\n"
        "  - [1.0, 2.0]\n"
        "обложка:\n"
        "  строка1: Первая строка\n"
        "  строка2: Вторая строка\n"
        f"  стикер: {стикер!r}\n"
        "---\n",
        encoding="utf-8",
    )
    return путь


def _записать_стиль(tmp_path: Path, дополнение: str = "") -> Path:
    путь = tmp_path / "стиль.md"
    путь.write_text(
        "```yaml\n"
        "обложка:\n"
        "  стикеры: true\n"
        f"  шрифт_основной: {(КОРЕНЬ / 'assets/fonts/Unbounded.ttf').as_posix()}\n"
        f"  шрифт_акцента: {(КОРЕНЬ / 'assets/fonts/CormorantGaramondItalic.ttf').as_posix()}\n"
        f"{дополнение}"
        "```\n",
        encoding="utf-8",
    )
    return путь


def _собрать_png(параметры: dict, путь: Path) -> None:
    gen_cover.overlay_png(параметры, путь)
    with Image.open(путь) as изображение:
        assert изображение.size == (gen_cover.W, gen_cover.H)


def test_обложка_собирается_с_пустым_стикером(tmp_path: Path):
    параметры = gen_cover.параметры_обложки(
        _записать_ролик(tmp_path, ""), _записать_стиль(tmp_path)
    )

    _собрать_png(параметры, tmp_path / "обложка.png")


def test_обложка_собирается_без_папки_стикеров(
    tmp_path: Path, monkeypatch
):
    параметры = gen_cover.параметры_обложки(
        _записать_ролик(tmp_path, "несуществующий"), _записать_стиль(tmp_path)
    )
    отсутствующая_папка = tmp_path / "assets" / "stickers"
    monkeypatch.setattr(gen_cover, "СТИКЕРЫ", отсутствующая_папка)

    _собрать_png(параметры, tmp_path / "обложка.png")


def test_параметры_обложки_берут_акцент_и_тайминги_из_стиля(tmp_path: Path):
    параметры = gen_cover.параметры_обложки(
        _записать_ролик(tmp_path, ""),
        _записать_стиль(
            tmp_path,
            "  цвет_акцента: '#123456'\n"
            "  цвет_основной: '#654321'\n"
            "  длительность: 3.5\n"
            "  затухание: 0.7\n",
        ),
    )

    assert параметры["цвет_акцента"] == (18, 52, 86)
    assert параметры["цвет_основной"] == (101, 67, 33)
    assert параметры["длительность"] == 3.5
    assert параметры["затухание"] == 0.7


def test_параметры_обложки_разрешают_шрифты_умолчаний_из_ассетов(tmp_path: Path):
    путь_стиля = tmp_path / "стиль_без_шрифтов.md"
    путь_стиля.write_text("```yaml\nобложка:\n  стикеры: false\n```", encoding="utf-8")

    параметры = gen_cover.параметры_обложки(
        _записать_ролик(tmp_path, ""),
        путь_стиля,
    )

    assert параметры["шрифт_основной"] == "assets/fonts/Unbounded.ttf"
    assert параметры["шрифт_акцента"] == "assets/fonts/CormorantGaramondItalic.ttf"
