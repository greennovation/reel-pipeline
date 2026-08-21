#!/usr/bin/env python3
"""Детектор фальстартов/запинок в рилсах (порог длинного слова = скрытая запинка).

whisper не пишет фальстарты текстом — он схлопывает их в аномально длинное
слово (напр. «тот»[670.66-672.98]=2.32s прячет брошенный «это не БЯМ… ммм»).
Скрипт находит такие места по трём сигналам и сводит таблицу на ревью.

Сигналы:
  (a) растянутое слово    — длительность > DUR_TH (скрытый фальстарт/филлер)
  (b) fuzzy near-repeat   — первые N слов фразы повторяются в окне REPEAT_WIN
  (c) пауза/точный повтор  — gap > PAUSE_TH либо соседние одинаковые слова

Использование:
  python3 find_stutters.py                       # все планы plan/*.json
  python3 find_stutters.py plan/02_4d.json       # один план
Опционально первый-после-плана аргумент — путь к транскрипту
(по умолчанию transcripts/A001_C031.json).
"""
import json, re, sys, glob
from pathlib import Path

TJSON_DEFAULT = "transcripts/A001_C031.json"
DUR_TH = 1.4        # сек: любое слово длиннее — кандидат в скрытую запинку
SHORT_LEN = 4       # символов: «короткое» слово
SHORT_DUR = 0.55    # сек: короткое слово держится дольше → спрятана микро-запинка/пауза
PAUSE_TH = 0.45     # сек: микро-пауза внутри куска
REPEAT_WIN = 6.0    # сек: окно поиска fuzzy-повтора
REPEAT_N = 2        # сколько первых слов должны совпасть для near-repeat
OUT = "stutters_review.md"


def norm(t):
    return re.sub(r"[^\wа-яё@-]", "", t.lower())


def load_all_words(tjson):
    d = json.loads(Path(tjson).read_text(encoding="utf-8"))
    words = []
    for s in d["segments"]:
        for w in s.get("words", []):
            words.append({"t": w["word"].strip(), "s": round(w["start"], 2), "e": round(w["end"], 2)})
    # склейка переносов «какая» + «-то»
    merged = []
    for w in words:
        if w["t"].startswith("-") and merged:
            merged[-1]["t"] += w["t"]
            merged[-1]["e"] = w["e"]
        else:
            merged.append(dict(w))
    return merged


def piece_offsets(plan):
    """Список (piece_idx, src_start, src_end, reel_start) для маппинга."""
    out, t = [], 0.0
    for i, pc in enumerate(plan["pieces"]):
        dur = pc["end"] - pc["start"]
        out.append((i, pc["start"], pc["end"], t))
        t += dur
    return out


def src_to_reel(src_t, offsets):
    for i, a, b, r in offsets:
        if a - 0.05 <= src_t <= b + 0.05:
            return r + (src_t - a)
    return None


def fmt(t):
    if t is None:
        return "  —  "
    return f"{int(t//60)}:{t%60:04.1f}"


def ctx(words, idx, back=5, fwd=6):
    seg = words[max(0, idx - back): idx + fwd]
    return " ".join(w["t"] for w in seg)


def piece_of(src_t, offsets):
    for i, a, b, _ in offsets:
        if a - 0.05 <= src_t <= b + 0.05:
            return i
    return None


def detect(words, offsets):
    """Вернёт список кандидатов ВНУТРИ кусков рилса (стыки кусков отсекаются)."""
    in_reel = [(i, w) for i, w in enumerate(words)
               if piece_of(w["s"], offsets) is not None]
    cand = []
    seen = set()
    idxset = {i for i, _ in in_reel}

    for i, w in in_reel:
        dur = w["e"] - w["s"]
        pc = piece_of(w["s"], offsets)
        clean_len = len(norm(w["t"]))
        # (a) растянутое слово: либо длинное, либо КОРОТКОЕ слово держится подозрительно долго
        if dur > DUR_TH:
            cand.append(("растянутое слово", w["s"], dur, ctx(words, i)))
        elif clean_len <= SHORT_LEN and dur > SHORT_DUR:
            cand.append(("микро: короткое слово долго", w["s"], dur, ctx(words, i)))
        # (c) пауза — только если следующее слово в ТОМ ЖЕ куске (не стык склейки)
        if i + 1 in idxset and piece_of(words[i + 1]["s"], offsets) == pc:
            gap = words[i + 1]["s"] - w["e"]
            if gap > PAUSE_TH:
                cand.append(("пауза", w["e"], gap, ctx(words, i)))

    # (b) fuzzy near-repeat: первые REPEAT_N слов повторяются в окне (внутри одного куска)
    seq = [w for _, w in in_reel]
    for i in range(len(seq)):
        if piece_of(seq[i]["s"], offsets) is None:
            continue
        key = tuple(norm(seq[i + k]["t"]) for k in range(REPEAT_N) if i + k < len(seq))
        if len(key) < REPEAT_N or any(len(x) < 2 for x in key):
            continue
        pc_i = piece_of(seq[i]["s"], offsets)
        for j in range(i + REPEAT_N, len(seq)):
            if seq[j]["s"] - seq[i]["s"] > REPEAT_WIN:
                break
            if piece_of(seq[j]["s"], offsets) != pc_i:  # повтор через стык — не запинка
                continue
            key2 = tuple(norm(seq[j + k]["t"]) for k in range(REPEAT_N) if j + k < len(seq))
            if key2 == key:
                tag = (round(seq[i]["s"], 1), key)
                if tag not in seen:
                    seen.add(tag)
                    cand.append(("near-repeat ×2", seq[i]["s"],
                                 seq[j]["s"] - seq[i]["s"],
                                 f"«{' '.join(key)}…» @ {seq[i]['s']:.1f} → {seq[j]['s']:.1f}"))
                break
    cand.sort(key=lambda c: c[1])
    return cand


def main():
    args = [a for a in sys.argv[1:]]
    tjson = TJSON_DEFAULT
    plans = []
    for a in args:
        if a.endswith(".json") and "plan/" in a:
            plans.append(a)
        elif a.endswith(".json"):
            tjson = a
    if not plans:
        plans = sorted(glob.glob("plan/0*.json"))

    words = load_all_words(tjson)
    lines = [f"# Ревью запинок/фальстартов\n",
             f"> Транскрипт: `{tjson}` · порог слова {DUR_TH}s · паузы {PAUSE_TH}s · окно повтора {REPEAT_WIN}s\n",
             "Классификация: ✂ фальстарт (резать первый) · 🔁 риторика (НЕ резать) · ✄ филлер (подрезать)\n"]
    for pf in plans:
        plan = json.loads(Path(pf).read_text(encoding="utf-8"))
        offs = piece_offsets(plan)
        cand = detect(words, offs)
        name = Path(pf).stem
        lines.append(f"\n## {name} ({len(cand)} кандидатов)\n")
        lines.append("| рилс-тайм | исходник | тип | сигнал | контекст |")
        lines.append("|---|---|---|---|---|")
        for typ, src_t, val, context in cand:
            reel_t = src_to_reel(src_t, offs)
            v = f"{val:.2f}s" if typ != "near-repeat ×2" else f"+{val:.1f}s"
            lines.append(f"| {fmt(reel_t)} | {src_t:.2f} | {typ} | {v} | {context} |")
    Path(OUT).write_text("\n".join(lines), encoding="utf-8")
    print(f"OK → {OUT}")
    print("\n".join(lines[:3]))
    for pf in plans:
        plan = json.loads(Path(pf).read_text(encoding="utf-8"))
        c = detect(words, piece_offsets(plan))
        print(f"  {Path(pf).stem}: {len(c)} кандидатов")


if __name__ == "__main__":
    main()
