import importlib.util
from pathlib import Path

import gen_finale
import stitch_reel

from стиль import загрузить_стиль


def _стиль(tmp_path: Path, fps: int) -> dict:
    файл = tmp_path / f"стиль_{fps}.md"
    файл.write_text(
        f"```yaml\nформат:\n  кадров_в_секунду: {fps}\n```",
        encoding="utf-8",
    )
    return загрузить_стиль(файл)


def _шаблон_оркестратора():
    путь = Path(__file__).parents[1] / "templates" / "make_reel_TEMPLATE.py"
    spec = importlib.util.spec_from_file_location("шаблон_оркестратора", путь)
    assert spec and spec.loader
    шаблон = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(шаблон)
    return шаблон


def test_разная_частота_стиля_меняет_фильтр_тела(tmp_path: Path):
    низкая = stitch_reel.фильтр_тела(2.0, 0, _стиль(tmp_path, 25))
    высокая = stitch_reel.фильтр_тела(2.0, 0, _стиль(tmp_path, 50))

    assert "fps=25" in низкая
    assert "fps=50" in высокая
    assert низкая != высокая


def test_тело_и_финал_берут_частоту_из_одного_стиля(tmp_path: Path):
    стиль = _стиль(tmp_path, 48)

    фильтр_тела = stitch_reel.фильтр_тела(2.0, 0, стиль)
    фильтр_финала = _шаблон_оркестратора().видеофильтр(стиль)
    fps_финала, число_кадров = gen_finale.параметры_анимации(2.0, стиль)

    assert "fps=48" in фильтр_тела
    assert "fps=48" in фильтр_финала
    assert fps_финала == 48
    assert число_кадров == 96


def test_шаблонный_фильтр_берёт_частоту_из_стиля(tmp_path: Path):
    шаблон = _шаблон_оркестратора()

    низкая = шаблон.видеофильтр(_стиль(tmp_path, 25))
    высокая = шаблон.видеофильтр(_стиль(tmp_path, 50))

    assert "fps=25" in низкая
    assert "fps=50" in высокая
    assert низкая != высокая
