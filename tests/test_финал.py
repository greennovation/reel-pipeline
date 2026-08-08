import sys

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
