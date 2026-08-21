#!/usr/bin/env python3
"""ШАБЛОН плана нарезки рилса. Скопируй как build_<твоя_съёмка>.py и заполни.

Куски (start,end) по аудио — слова субтитров автоподтянутся из whisper-json.
Где whisper глотнул/переврал слова — задай явный dict-кусок {"span","words"}.
Правки распознавания: GLOBAL (по слову) + TIMED (по таймкоду).

Запуск: python3 build_<съёмка>.py <reel_id>
"""
import json, sys
from pathlib import Path

# Правки whisper: (start_time, исходное_слово) -> новое ("" = убрать из субтитров)
TIMED = {
    # (123.45, "Charge"): "ChatGPT",
}

# Правки whisper по слову (на всех вхождениях)
GLOBAL = {
    # "промтов": "промптов", "Шпучка": "Шипучка", "Неронка": "Нейронка",
    # "Charge": "ChatGPT",  # whisper часто слышит ChatGPT как «Charge GPT»
}

# Источники: id -> (видео_SDR, транскрипт_json). Видео — после avconvert (см. PIPELINE §2).
SOURCES = {
    # "myreel": ("raw_sdr/SHOT.mov", "transcripts/SHOT.json"),
}

NOSUB = {}   # id -> set(индексов кусков без субтитров)

# Куски каждого рилса. Вырезай фальстарты/дубли/паузы — оставляй чистый дубль.
REELS = {
    # "myreel": [
    #     (12.30, 18.75),                       # обычный кусок: слова из json
    #     {"span": (90.5, 107.0), "words": [    # явный кусок (whisper глотнул участок)
    #         ("Каждую", 90.56, 90.98), ("неделю", 90.98, 91.34),
    #     ]},
    # ],
}

SHOOT = "TEMPLATE"   # префикс плана/выхода: plan/<SHOOT>_<id>.json


def load_words(tjson):
    data = json.loads(Path(tjson).read_text(encoding="utf-8"))
    raw = []
    for seg in data["segments"]:
        for w in seg.get("words", []):
            raw.append({"text": w["word"].strip(), "start": round(w["start"], 2), "end": round(w["end"], 2)})
    words = []
    for w in raw:
        if w["text"].startswith("-") and words:   # склейка дефисных хвостов
            words[-1]["text"] += w["text"]; words[-1]["end"] = w["end"]
        else:
            words.append(dict(w))
    return words


def fix(w):
    t = TIMED.get((w["start"], w["text"]))
    if t is None:
        t = GLOBAL.get(w["text"], w["text"])
    return t


def build(name):
    src, tjson = SOURCES[name]
    words = load_words(tjson)
    nosub = NOSUB.get(name, set())
    pieces = []
    for idx, item in enumerate(REELS[name]):
        if isinstance(item, dict):                 # явный кусок
            a, b = item["span"]
            wsrc = item["words"] if "words" in item else [
                (w["text"], w["start"], w["end"]) for w in words
                if item["auto"][0] - 0.03 <= w["start"] <= item["auto"][1] - 0.10]
            pw = []
            for t, s, e in wsrc:
                ft = fix({"text": t, "start": s, "end": e})
                if ft != "":
                    pw.append({"text": ft, "start": s, "end": e})
            pieces.append({"start": round(a, 2), "end": round(b, 2),
                           "words": [] if idx in nosub else pw})
            continue
        a, b = item                                # кусок по таймингам
        pw = []
        for w in words:
            if a - 0.03 <= w["start"] <= b - 0.10:
                t = fix(w)
                if t == "":
                    if pw: pw[-1]["end"] = w["end"]
                    continue
                pw.append({"text": t, "start": w["start"], "end": w["end"]})
        if not pw:
            raise SystemExit(f"{name}: пустой кусок {a}-{b}")
        nxt = next((w["start"] for w in words if w["start"] > pw[-1]["start"] + 0.01), None)
        last_end = min(pw[-1]["end"], pw[-1]["start"] + 1.4)
        end = max(b, last_end + 0.12)
        if nxt is not None:
            end = min(end, nxt - 0.02)
        end = max(end, last_end)
        start = min(a, pw[0]["start"] - 0.05)
        pieces.append({"start": round(start, 2), "end": round(end, 2),
                       "words": [] if idx in nosub else pw})
    plan = {"src": src, "out": f"cut/{SHOOT}_{name}.mp4", "pieces": pieces}
    Path("plan").mkdir(exist_ok=True)
    Path(f"plan/{SHOOT}_{name}.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    dur = sum(p["end"] - p["start"] for p in pieces)
    nw = sum(len(p["words"]) for p in pieces)
    print(f"{SHOOT}_{name}: {dur:.1f}s, {len(pieces)} кусков, {nw} слов -> plan/{SHOOT}_{name}.json")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(REELS)):
        build(n)
