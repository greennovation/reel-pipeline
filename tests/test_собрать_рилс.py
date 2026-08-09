import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import собрать_рилс


def _записать_ролик(
    корень: Path, *, финал: str = "куски: []", имя: str = "тест"
) -> Path:
    папка = корень / "Рилсы"
    папка.mkdir(parents=True, exist_ok=True)
    путь = папка / "мой-ролик.md"
    путь.write_text(
        "---\n"
        f"ролик: {имя}\n"
        "исходник: IMG_0421.MOV\n"
        "куски:\n"
        "  - отрезок: [1.0, 2.0]\n"
        "    слова:\n"
        "      - [Тест, 1.1, 1.4]\n"
        "без_субтитров: []\n"
        "финал:\n"
        "  исходник: IMG_0421.MOV\n"
        f"  {финал}\n"
        "---\n",
        encoding="utf-8",
    )
    return путь


def _записать_стиль(корень: Path, fps: int = 30) -> Path:
    путь = корень / "стиль.md"
    путь.write_text(
        "```yaml\n"
        "формат:\n"
        "  ширина: 1080\n"
        "  высота: 1920\n"
        f"  кадров_в_секунду: {fps}\n"
        "распознавание:\n"
        "  модель: tiny\n"
        "  язык: ru\n"
        "музыка:\n"
        "  громкость: 0.17\n"
        "  режим: upbeat\n"
        "финал:\n"
        "  подпись: Подпись\n"
        "  начало_до_конца: 2.5\n"
        "  хвост: 0.5\n"
        "```\n",
        encoding="utf-8",
    )
    return путь


def _транскрипт(корень: Path) -> Path:
    путь = корень / "transcripts" / "IMG_0421.json"
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(
        json.dumps(
            {"segments": [{"words": [{"word": "Тест", "start": 1.1, "end": 1.4}]}]}
        ),
        encoding="utf-8",
    )
    return путь


def _подменить_программы(monkeypatch: pytest.MonkeyPatch, команды: list[list[str]]) -> None:
    """Имитирует только побочные эффекты стадий, не требуя видеоинструментов."""

    def запуск(команда, **_kwargs):
        команда = [str(часть) for часть in команда]
        команды.append(команда)
        имя = Path(команда[0]).name
        if имя == "ffprobe":
            if "format=duration" in команда:
                return SimpleNamespace(stdout="10.0\n")
            return SimpleNamespace(stdout="width=1920\nheight=1080\nrotation=-90\n")
        if имя == "ffmpeg" and команда[1:] == ["-version"]:
            return SimpleNamespace(stdout="ffmpeg version 4.4.1\n")
        if имя == "avconvert":
            Path(команда[команда.index("-o") + 1]).touch()
        elif имя == "ffmpeg":
            Path(команда[-1]).touch()
        elif имя == "whisper":
            wav = Path(команда[1])
            (wav.parent / f"{wav.stem}.json").write_text(
                json.dumps(
                    {"segments": [{"words": [{"word": "Тест", "start": 1.1, "end": 1.4}]}]}
                ),
                encoding="utf-8",
            )
        elif команда[0] == sys.executable:
            скрипт = Path(команда[1]).name
            if скрипт == "stitch_reel.py":
                план = json.loads(Path(команда[2]).read_text(encoding="utf-8"))
                выход = Path(команда[2]).parents[1] / план["out"]
            elif скрипт in {"gen_finale.py", "gen_polish.py", "gen_music.py"}:
                выход = Path(команда[3])
            elif скрипт == "gen_cover.py":
                выход = Path(команда[4])
            else:
                raise AssertionError(f"неизвестная стадия: {команда}")
            выход.parent.mkdir(parents=True, exist_ok=True)
            выход.touch()
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(собрать_рилс, "запустить", запуск)


def test_существующие_sdr_и_транскрипт_не_пересоздаются(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ролик = _записать_ролик(tmp_path)
    стиль = _записать_стиль(tmp_path)
    raw = tmp_path / "raw" / "IMG_0421.MOV"
    raw.parent.mkdir()
    raw.touch()
    sdr = tmp_path / "raw_sdr" / "IMG_0421.mov"
    sdr.parent.mkdir()
    sdr.touch()
    _транскрипт(tmp_path)
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)

    итог = собрать_рилс.собрать(ролик, стиль, tmp_path)

    программы = [команда[0] for команда in команды]
    assert "avconvert" not in программы
    assert "whisper" not in программы
    assert итог == tmp_path / "cut" / "тест.mp4"
    команды_шагов = [команда for команда in команды if команда[0] == sys.executable]
    assert [Path(команда[1]).name for команда in команды_шагов] == [
        "stitch_reel.py",
        "gen_finale.py",
        "gen_polish.py",
        "gen_music.py",
        "gen_cover.py",
    ]
    assert all(команда[0] == sys.executable for команда in команды_шагов)


def test_слишком_старый_ffmpeg_сообщает_найденную_и_минимальную_версии(
    monkeypatch: pytest.MonkeyPatch,
):
    команды: list[list[str]] = []

    def запуск(команда, **_kwargs):
        команды.append(команда)
        return SimpleNamespace(stdout="ffmpeg version 4.2.2 Copyright")

    monkeypatch.setattr(собрать_рилс, "запустить", запуск)

    with pytest.raises(собрать_рилс.ОшибкаПользователя) as поймано:
        собрать_рилс.проверить_ffmpeg()

    сообщение = str(поймано.value)
    assert "ffmpeg" in сообщение
    assert "4.2.2" in сообщение
    assert "4.4" in сообщение
    assert команды == [["ffmpeg", "-version"]]


def test_достаточная_версия_ffmpeg_проходит_проверку_и_не_мешает_сборке(
    monkeypatch: pytest.MonkeyPatch,
):
    команды: list[list[str]] = []

    def запуск(команда, **_kwargs):
        команды.append(команда)
        return SimpleNamespace(stdout="ffmpeg version 4.4.1 Copyright")

    monkeypatch.setattr(собрать_рилс, "запустить", запуск)

    собрать_рилс.проверить_ffmpeg()

    assert команды == [["ffmpeg", "-version"]]


def test_отсутствующий_sdr_готовится_через_нужный_пресет(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ролик = _записать_ролик(tmp_path)
    стиль = _записать_стиль(tmp_path)
    raw = tmp_path / "raw" / "IMG_0421.MOV"
    raw.parent.mkdir()
    raw.touch()
    _транскрипт(tmp_path)
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)

    собрать_рилс.собрать(ролик, стиль, tmp_path)

    avconvert = next(команда for команда in команды if команда[0] == "avconvert")
    assert avconvert[avconvert.index("-p") + 1] == "Preset1920x1080"


def test_отсутствующий_транскрипт_берёт_модель_язык_и_словные_тайминги(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path))
    исходник = tmp_path / "raw" / "IMG_0421.MOV"
    исходник.parent.mkdir()
    исходник.touch()
    транскрипт = tmp_path / "transcripts" / "IMG_0421.json"
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)

    wav = собрать_рилс.подготовить_транскрипт(исходник, транскрипт, стиль)

    ffmpeg, whisper = команды
    assert ffmpeg[ffmpeg.index("-ac") + 1] == "1"
    assert ffmpeg[ffmpeg.index("-ar") + 1] == "16000"
    assert whisper[whisper.index("--model") + 1] == "tiny"
    assert whisper[whisper.index("--language") + 1] == "ru"
    assert whisper[whisper.index("--word_timestamps") + 1] == "True"
    assert wav == tmp_path / "transcripts" / "IMG_0421.wav"


@pytest.mark.parametrize("fps", [24, 50])
def test_частота_стиля_попадает_в_команду_нарезки_финала(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fps: int
):
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path, fps))
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)

    собрать_рилс._вырезать_финал(tmp_path / "raw_sdr" / "IMG.mov", [(1.0, 2.0)], tmp_path, стиль)

    команда = команды[0]
    assert f"fps={fps}" in команда[команда.index("-vf") + 1]
    assert команда[команда.index("-r") + 1] == str(fps)


def test_нарезка_финала_не_задаёт_кодек_и_параметры_кодирования(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path))
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)

    собрать_рилс._вырезать_финал(tmp_path / "raw_sdr" / "IMG.mov", [(1.0, 2.0)], tmp_path, стиль)

    assert not {"-c:v", "-preset", "-crf", "-pix_fmt", "-c:a", "-b:a"} & set(команды[0])


def test_куски_финала_нормализуются_и_присоединяются(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    тело = tmp_path / "cut" / "тест.mp4"
    тело.parent.mkdir()
    тело.touch()
    sdr = tmp_path / "raw_sdr" / "IMG_0421.mov"
    sdr.parent.mkdir()
    sdr.touch()
    raw = tmp_path / "raw" / "IMG_0421.MOV"
    raw.parent.mkdir()
    raw.touch()
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)
    описание = {
        "исходник": "IMG_0421.MOV",
        "финал": {"исходник": "IMG_0421.MOV", "куски": [[3.0, 4.0]]},
    }
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path, 48))
    база = tmp_path / "cut" / "тест_full.mp4"

    собрать_рилс.присоединить_финал(тело, база, описание, tmp_path, стиль)

    команды_ffmpeg = [команда for команда in команды if команда[0] == "ffmpeg"]
    assert "fps=48" in команды_ffmpeg[0][команды_ffmpeg[0].index("-vf") + 1]
    склейка = команды_ffmpeg[1]
    assert "-filter_complex" in склейка
    assert "concat=n=2" in склейка[склейка.index("-filter_complex") + 1]
    assert "copy" not in склейка
    assert база.is_file()


def test_только_план_не_запускает_внешних_программ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ролик = _записать_ролик(tmp_path)
    стиль = _записать_стиль(tmp_path)
    вызовы: list[object] = []
    monkeypatch.setattr(собрать_рилс, "запустить", lambda *_args, **_kwargs: вызовы.append(None))

    assert собрать_рилс.main([str(ролик), "--стиль", str(стиль), "--корень", str(tmp_path), "--только-план"]) == 0

    план = json.loads((tmp_path / "plan" / "тест.json").read_text(encoding="utf-8"))
    assert план["out"] == "cut/тест.mp4"
    assert вызовы == []


def test_отсутствующий_исходник_объясняет_куда_его_положить(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    ролик = _записать_ролик(tmp_path)
    стиль = _записать_стиль(tmp_path)

    assert собрать_рилс.main([str(ролик), "--стиль", str(стиль), "--корень", str(tmp_path)]) == 1

    ошибка = capsys.readouterr().err
    assert "IMG_0421.MOV" in ошибка
    assert "raw/" in ошибка
    assert "Traceback" not in ошибка


def test_ландшафтная_ориентация_предупреждает_до_монтажа(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    исходник = tmp_path / "raw" / "IMG_0421.MOV"
    исходник.parent.mkdir()
    исходник.touch()

    monkeypatch.setattr(
        собрать_рилс,
        "запустить",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="width=1920\nheight=1080\nrotation=0\n"
        ),
    )

    собрать_рилс.предупредить_об_ориентации(исходник, tmp_path)

    assert "не выглядит портретной" in capsys.readouterr().err


def test_сбой_проверки_ориентации_не_останавливает_монтаж(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    исходник = tmp_path / "raw" / "IMG_0421.MOV"
    исходник.parent.mkdir()
    исходник.touch()
    monkeypatch.setattr(
        собрать_рилс,
        "запустить",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, ["ffprobe"])
        ),
    )

    собрать_рилс.предупредить_об_ориентации(исходник, tmp_path)

    assert "Монтаж продолжается" in capsys.readouterr().err


def test_whisper_без_json_останавливает_сборку_без_тихих_субтитров(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path))
    исходник = tmp_path / "raw" / "IMG_0421.MOV"
    исходник.parent.mkdir()
    исходник.touch()
    транскрипт = tmp_path / "transcripts" / "IMG_0421.json"

    def запуск(команда, **_kwargs):
        if команда[0] == "ffmpeg":
            Path(команда[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(команда[-1]).touch()
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(собрать_рилс, "запустить", запуск)

    with pytest.raises(собрать_рилс.ОшибкаПользователя, match="не создал транскрипт"):
        собрать_рилс.подготовить_транскрипт(исходник, транскрипт, стиль)

    assert not транскрипт.with_suffix(".wav").exists()


def test_сбой_обложки_сохраняет_готовое_тело(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    тело = tmp_path / "cut" / "тест.mp4"
    тело.parent.mkdir()
    тело.write_text("тело", encoding="utf-8")
    стиль_файл = _записать_стиль(tmp_path)
    стиль = собрать_рилс.загрузить_стиль(стиль_файл)

    monkeypatch.setattr(
        собрать_рилс,
        "присоединить_финал",
        lambda _тело, база, *_args: shutil.copy2(тело, база),
    )

    def запуск(команда, **_kwargs):
        if команда[0] == "ffprobe":
            return SimpleNamespace(stdout="10.0\n")
        имя_скрипта = Path(команда[1]).name
        if имя_скрипта != "gen_cover.py":
            Path(команда[3]).touch()
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(собрать_рилс, "запустить", запуск)

    with pytest.raises(собрать_рилс.ОшибкаПользователя, match="gen_cover"):
        собрать_рилс.обработать_готовое(
            tmp_path / "Рилсы" / "мой-ролик.md",
            тело,
            {"ролик": "тест"},
            tmp_path,
            стиль_файл,
            стиль,
        )

    assert тело.read_text(encoding="utf-8") == "тело"


def test_пустой_финал_не_запускает_нарезку(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    тело = tmp_path / "тело.mp4"
    база = tmp_path / "база.mp4"
    тело.touch()
    команды: list[list[str]] = []
    _подменить_программы(monkeypatch, команды)
    описание = {
        "исходник": "IMG_0421.MOV",
        "финал": {"исходник": "IMG_0421.MOV", "куски": []},
    }
    стиль = собрать_рилс.загрузить_стиль(_записать_стиль(tmp_path))

    собрать_рилс.присоединить_финал(тело, база, описание, tmp_path, стиль)

    assert база.is_file()
    assert команды == []
