import sys
from pathlib import Path

import gen_finale


def test_пустая_подпись_пропускает_финал_без_ffmpeg(
    monkeypatch, capsys
):
    """Пустая подпись отключает финал до чтения видео и запуска ffmpeg."""
    monkeypatch.setattr(
        gen_finale,
        "загрузить_стиль",
        lambda путь: {"финал": {"подпись": "   "}},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["gen_finale.py", "исходник.mp4", "готовый.mp4", "стиль.md"],
    )

    def не_должно_выполняться(*_args, **_kwargs):
        raise AssertionError("при пустой подписи финал не должен запускаться")

    monkeypatch.setattr(gen_finale, "dur", не_должно_выполняться)
    monkeypatch.setattr(gen_finale, "run", не_должно_выполняться)

    assert gen_finale.main() is False
    assert "Финал пропущен" in capsys.readouterr().out


def test_стиль_по_умолчанию_задаёт_частоту_и_подпись_финала(
    monkeypatch, tmp_path: Path
):
    """Запуск без третьего аргумента читает стандартный файл фирменного стиля."""
    пути_стиля, кадры, подписи, команды = [], [], [], []

    def загрузить(путь):
        пути_стиля.append(путь)
        return {
            "формат": {"кадров_в_секунду": 48},
            "финал": {"подпись": "Подпись из стиля"},
        }

    class ПустойКадр:
        def save(self, путь):
            кадры.append(путь)

    monkeypatch.setattr(gen_finale, "загрузить_стиль", загрузить)
    monkeypatch.setattr(gen_finale, "dur", lambda _: 2.0)
    monkeypatch.setattr(gen_finale.tempfile, "mkdtemp", lambda prefix: str(tmp_path))
    def кадр(_время, подпись):
        подписи.append(подпись)
        return ПустойКадр()

    monkeypatch.setattr(gen_finale, "frame", кадр)
    monkeypatch.setattr(gen_finale, "run", lambda команда: команды.append(команда))
    monkeypatch.setattr(sys, "argv", ["gen_finale.py", "исходник.mp4", "готовый.mp4"])

    assert gen_finale.main() is True
    assert пути_стиля == ["Фирменный стиль.md"]
    assert len(кадры) == 144
    assert set(подписи) == {"Подпись из стиля"}
    assert "48" == команды[1][команды[1].index("-framerate") + 1]
