# 🎬 Reel Pipeline — переносимый тулкит для монтажа рилсов

Монтаж вертикальных рилсов из съёмки на iPhone: цвет «как на айфоне», субтитры,
фирменный финал, обложка — **одной командой**, без вечеров в редакторе.

Это **чистый переносимый набор**: движки + шаблоны + инструкция, без чужих видео
и личных данных. Сделан для канала [@aishipuchka](https://t.me/aishipuchka) и отдан вам.

---

## 🚀 Самый простой способ — через Claude Code

Не хотите разбираться в командах? И не надо.

1. Склонируйте репозиторий себе:
   ```bash
   git clone https://github.com/Voronik1801/reel_pipline.git
   cd reel_pipline
   ```
2. Откройте папку в [Claude Code](https://claude.com/claude-code) и напишите:
   > Прочитай PIPELINE.md и README.md, проверь и доустанови всё, что нужно для
   > работы пайплайна, потом помоги смонтировать рилс из моей съёмки.
3. Claude Code сам поставит зависимости, прогонит `pipeline_check.sh`, заполнит
   шаблоны под вашу съёмку и соберёт рилс. Вуаля 🪄

Вся логика и «правила, выученные кровью» лежат в **[PIPELINE.md](PIPELINE.md)** —
это single source of truth и для вас, и для агента.

---

## 🧩 Что входит

- **Документы:** [`PIPELINE.md`](PIPELINE.md) (мастер-инструкция по шагам), `pipeline_check.sh` (проверка окружения).
- **Движки** (трогать не нужно): `cut_reel`, `stitch_reel`, `sub_plashka`,
  `gen_finale`, `gen_cover`, `gen_polish`, `gen_music`, `gen_scheme`,
  `find_stutters`, `find_deadair`, `gen_lut`.
- **Шаблоны** (копируете под свою съёмку): `templates/build_TEMPLATE.py`,
  `templates/make_reel_TEMPLATE.py`.
- **Ассеты:** шрифты (Google Fonts) в `assets/fonts/`. Маскоты-стикеры — свои,
  см. `assets/stickers/README.md`.

---

## ⚙️ Требования

> ⚠️ **Только macOS.** Нативный HDR→SDR-тонмап (цвет «как на айфоне») даёт
> исключительно Apple `avconvert`. На Linux/Windows цвет будет блёклым/пересвеченным.

### 1. Системные инструменты

| Инструмент | Зачем | Установка |
|---|---|---|
| **ffmpeg / ffprobe** | весь видео/аудио-конвейер (crop, зум, overlay, concat) | `brew install ffmpeg` |
| **avconvert** | HDR→SDR-цвет «как на айфоне» | встроен в macOS, ставить не нужно |
| **Python 3.10+** | движки пайплайна | `brew install python` |

### 2. Python-пакеты

```bash
pip install -U openai-whisper        # транскрипция речи с word-таймингами (CPU ок)
pip install pillow numpy             # субтитры (PNG-overlay) и утилиты
```

> `openai-whisper` при первом запуске сам скачает модель (`small` ≈ 0.5 ГБ,
> `medium` ≈ 1.5 ГБ для финального QA). Нужен установленный `ffmpeg` — whisper
> использует его под капотом. Остальное (`pathlib`, `subprocess`, `json`,
> `math`, `argparse`) — из стандартной библиотеки Python.

### 3. Опционально

```bash
pip install rembg onnxruntime        # снять фон у стикеров-маскотов (модель u2net ~170 МБ)
```

### 4. Проверка

```bash
bash pipeline_check.sh               # покажет, чего не хватает
```

---

## ⚡ Быстрый старт (вручную)

```bash
# 1) положите съёмку в raw/, маскоты — в assets/stickers/
# 2) цвет «как на айфоне» (HDR -> SDR):
avconvert -p Preset1920x1080 -s raw/SHOT.MOV -o raw_sdr/SHOT.mov --replace
# 3) аудио + транскрипт со словными таймингами:
ffmpeg -i raw/SHOT.MOV -ac 1 -ar 16000 -vn transcripts/SHOT.wav
whisper transcripts/SHOT.wav --model small --language Russian \
    --word_timestamps True --output_format json --output_dir transcripts
# 4) опишите рилс в своих копиях шаблонов:
cp templates/build_TEMPLATE.py build_myshoot.py            # заполнить SOURCES / REELS
cp templates/make_reel_TEMPLATE.py make_reel_myshoot.py    # заполнить FINALE и путь к Markdown-роликам
# 5) рендер:
python3 build_myshoot.py myreel                            # план -> plan/*.json
python3 make_reel_myshoot.py myreel                        # готовый рилс -> cut/*.mp4
```

Полная инструкция со всеми шагами, правилами и справочником — в **[PIPELINE.md](PIPELINE.md)**.

---

## 🎞 Что получается на выходе

**1080×1920, частота из `формат.кадров_в_секунду` в «Фирменный стиль.md»
(по умолчанию 30), SDR (bt709), стерео 48k**, цвет как на iPhone, субтитры с
пословной подсветкой, фирменный финал с «ПШШ» и хук-обложка на первые 2 секунды.

Два сценария:
- **A — рилс из длинной съёмки:** нарезка говорящей головы, удаление дублей и
  филлеров, субтитры, финал, обложка, музыка.
- **B — склейка / коллаб:** соединение нескольких клипов с субтитрами на нужный момент.

---

## 🔒 Что НЕ входит (личное, по дизайну)

Видео, транскрипты, планы, готовые рилсы и конкретные `build_<дата>.py`.
`.gitignore` блокирует их от случайного коммита. Папки `raw/ raw_sdr/
transcripts/ plan/ cut/` создаются при первом запуске.

---

## 📄 Лицензия

Забирайте, пользуйтесь, делитесь. Если зашло — подписывайтесь на
[@aishipuchka](https://t.me/aishipuchka). Всем пшшш 💨
