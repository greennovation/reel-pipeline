#!/usr/bin/env bash
# Проверка окружения для reel-пайплайна (macOS/Linux). Запуск: bash pipeline_check.sh
# На Windows используйте кроссплатформенную версию: python3 pipeline_check.py
set -u
ok(){ printf "  ✅ %s\n" "$1"; }
no(){ printf "  ❌ %s — %s\n" "$1" "$2"; FAIL=1; }
FAIL=0
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

проверить_ffmpeg(){
  local output check
  if ! output="$(ffmpeg -version 2>&1)"; then
    no "ffmpeg" "brew install ffmpeg"
  elif check="$(printf '%s\n' "$output" | python3 "$SCRIPT_DIR/ffmpeg_version.py" 2>&1)"; then
    ok "ffmpeg $check"
  else
    no "ffmpeg" "$check"
  fi
}

echo "== Инструменты =="
command -v ffmpeg >/dev/null && проверить_ffmpeg || no "ffmpeg" "brew install ffmpeg"
command -v ffprobe >/dev/null && ok "ffprobe" || no "ffprobe" "идёт с ffmpeg"
command -v whisper >/dev/null && ok "whisper (openai)" || no "whisper" "pip install -U openai-whisper"
command -v avconvert >/dev/null && ok "avconvert (Apple HDR→SDR, эталон)" || printf "  ⚠️  %s — %s\n" "avconvert" "нет (только macOS); движок сам переключится на ffmpeg zscale+tonemap, если он собран с этим фильтром"
python3 -c "import PIL" 2>/dev/null && ok "Pillow (субтитры)" || no "Pillow" "pip install pillow"
python3 -c "import numpy" 2>/dev/null && ok "numpy" || no "numpy" "pip install numpy"
echo "== Ассеты =="
[ -f assets/fonts/Unbounded.ttf ] && ok "шрифт Unbounded" || no "Unbounded.ttf" "положи в assets/fonts/"
[ -d assets/stickers ] && ok "стикеры ($(ls assets/stickers/*.png 2>/dev/null|wc -l|tr -d ' ') шт)" || no "assets/stickers/" "маскоты для обложек"
echo "== Папки =="
for d in raw transcripts plan cut; do
  if [ -d "$d" ]; then ok "$d/"; else mkdir -p "$d"; ok "$d/ (создана)"; fi
done
echo ""
[ $FAIL -eq 0 ] && echo "✅ Окружение готово." || echo "⚠️  Есть пропуски — см. выше."
