from pathlib import Path
from types import SimpleNamespace

import pytest

import тонмап


def _подменить_путь_без_avconvert(monkeypatch: pytest.MonkeyPatch) -> None:
    """Имитирует отсутствие avconvert в PATH, не трогая реальный PATH машины."""
    monkeypatch.setattr(тонмап.shutil, "which", lambda имя: None)


def _подменить_путь_с_avconvert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        тонмап.shutil, "which", lambda имя: "/usr/bin/avconvert" if имя == "avconvert" else None
    )


def test_avconvert_в_path_даёт_способ_apple(monkeypatch: pytest.MonkeyPatch):
    _подменить_путь_с_avconvert(monkeypatch)

    способ = тонмап.выбрать_способ()

    assert способ == тонмап.СПОСОБ_APPLE


def test_без_avconvert_но_с_zscale_даёт_способ_ffmpeg(monkeypatch: pytest.MonkeyPatch):
    _подменить_путь_без_avconvert(monkeypatch)

    def запустить(команда, **_kwargs):
        assert команда[0] == "ffmpeg"
        return SimpleNamespace(stdout="... zscale             V->V  Apply resizing, colorspace and bit depth conversion.\n")

    способ = тонмап.выбрать_способ(запустить=запустить)

    assert способ == тонмап.СПОСОБ_FFMPEG


def test_без_avconvert_и_без_zscale_даёт_понятную_ошибку(monkeypatch: pytest.MonkeyPatch):
    _подменить_путь_без_avconvert(monkeypatch)

    def запустить(команда, **_kwargs):
        return SimpleNamespace(stdout="... scale               V->V  Scale the input video size.\n")

    with pytest.raises(тонмап.ОшибкаТонмапа) as поймано:
        тонмап.выбрать_способ(запустить=запустить)

    сообщение = str(поймано.value)
    assert "avconvert" in сообщение
    assert "zscale" in сообщение
    assert "choco" in сообщение  # инструкция для Windows видна в тексте ошибки


def test_отсутствующий_ffmpeg_при_проверке_zscale_тоже_даёт_ошибку(
    monkeypatch: pytest.MonkeyPatch,
):
    _подменить_путь_без_avconvert(monkeypatch)

    def запустить(команда, **_kwargs):
        raise FileNotFoundError(команда[0])

    with pytest.raises(тонмап.ОшибкаТонмапа):
        тонмап.выбрать_способ(запустить=запустить)


def test_способ_apple_повторяет_прежнюю_команду_avconvert_байт_в_байт(tmp_path: Path):
    """Регрессия: та же команда и порядок аргументов, что были в собрать_рилс.py."""
    вход = tmp_path / "IMG_0421.MOV"
    выход = tmp_path / "raw_sdr" / "IMG_0421.mov"
    команды: list[list[str]] = []

    def запустить(команда, **_kwargs):
        команды.append([str(часть) for часть in команда])
        return SimpleNamespace(stdout="")

    тонмап.привести_к_sdr(вход, выход, тонмап.СПОСОБ_APPLE, запустить=запустить)

    assert команды == [
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
    ]


def test_способ_ffmpeg_на_hdr_входе_строит_тонмап_и_sdr_теги(tmp_path: Path):
    вход = tmp_path / "IMG_0421.MOV"
    выход = tmp_path / "raw_sdr" / "IMG_0421.mov"
    команды: list[list[str]] = []

    def запустить(команда, **_kwargs):
        команда = [str(часть) for часть in команда]
        команды.append(команда)
        if команда[0] == "ffprobe":
            return SimpleNamespace(stdout="arib-std-b67\n")
        return SimpleNamespace(stdout="")

    тонмап.привести_к_sdr(вход, выход, тонмап.СПОСОБ_FFMPEG, запустить=запустить)

    ffprobe, ffmpeg = команды
    assert ffprobe[0] == "ffprobe"
    assert str(вход) in ffprobe

    assert ffmpeg[0] == "ffmpeg"
    фильтр = ffmpeg[ffmpeg.index("-vf") + 1]
    assert "zscale" in фильтр
    assert "tonemap=hable" in фильтр
    assert "desat=0" in фильтр
    for флаг, значение in [
        ("-color_primaries", "bt709"),
        ("-color_trc", "bt709"),
        ("-colorspace", "bt709"),
    ]:
        assert ffmpeg[ffmpeg.index(флаг) + 1] == значение
    assert ffmpeg[ffmpeg.index("-c:a") + 1] == "copy"
    assert ffmpeg[-1] == str(выход)


def test_способ_ffmpeg_на_sdr_входе_не_запускает_тонмап(tmp_path: Path):
    вход = tmp_path / "IMG_0421.MOV"
    выход = tmp_path / "raw_sdr" / "IMG_0421.mov"
    команды: list[list[str]] = []

    def запустить(команда, **_kwargs):
        команда = [str(часть) for часть in команда]
        команды.append(команда)
        if команда[0] == "ffprobe":
            return SimpleNamespace(stdout="bt709\n")
        return SimpleNamespace(stdout="")

    тонмап.привести_к_sdr(вход, выход, тонмап.СПОСОБ_FFMPEG, запустить=запустить)

    ffmpeg = команды[1]
    фильтр = ffmpeg[ffmpeg.index("-vf") + 1]
    assert "zscale" not in фильтр
    assert "tonemap" not in фильтр


@pytest.mark.parametrize("трансфер", ["arib-std-b67", "smpte2084"])
def test_определить_hdr_распознаёт_hlg_и_pq(tmp_path: Path, трансфер: str):
    вход = tmp_path / "IMG_0421.MOV"

    def запустить(команда, **_kwargs):
        return SimpleNamespace(stdout=f"{трансфер}\n")

    assert тонмап.определить_hdr(вход, запустить=запустить) is True


def test_определить_hdr_не_путает_обычный_sdr_с_hdr(tmp_path: Path):
    вход = tmp_path / "IMG_0421.MOV"

    def запустить(команда, **_kwargs):
        return SimpleNamespace(stdout="bt709\n")

    assert тонмап.определить_hdr(вход, запустить=запустить) is False


def test_неизвестный_способ_даёт_ошибку(tmp_path: Path):
    with pytest.raises(тонмап.ОшибкаТонмапа):
        тонмап.привести_к_sdr(
            tmp_path / "вход.mov", tmp_path / "выход.mov", "неведомый",
            запустить=lambda *_a, **_k: SimpleNamespace(stdout=""),
        )
