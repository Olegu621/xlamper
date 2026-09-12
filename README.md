<div align="center">

# 🕹️ C3 XLAMPER — Apps

**Облачный каталог игр и приложений для карманного «флиппера» на ESP32-C3**

[![Apps: 12](https://img.shields.io/badge/Apps-12-blue)](#каталог)
[![XLA VM](https://img.shields.io/badge/VM-XLA%20bytecode-orange)](tools/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

*Snake · Tetris · 2048 · Pong · Slots · Mines · Wires · Spinner · Coin Flip · Root Bear*

</div>

---

## 🎮 Как это работает

**C3 XLAMPER** — открытая карманная консоль на ESP32-C3 Super Mini
(OLED SSD1306 128×64, аналоговый стик, пьезо-спикер). Прошивка — тонкая
оболочка: при старте она синхронизирует этот каталог по Wi-Fi, и **любая
игра скачивается, запускается и удаляется** — на борту хранится только
список. Хочешь новую игру? Просто добавь `.xla` в этот репозиторий —
её увидят все консоли мира.

```
 ┌─────────┐   Wi-Fi    ┌──────────────┐   download → run → delete
 │ XLAMPER │◄──────────►│  этот репо   │──►  RAM (без кэша!)
 └─────────┘  manifest  └──────────────┘
```

- **Никакой установки**: приложение = один файл `.xla` (~1–2 КБ)
- **Бесконечный каталог**: консоль хранит 0 байт игр
- **Рекорды** — в NVS консоли, ключ `<TITLE>_best`

## 📦 Каталог

| Игра | Описание | Управление |
| ------ | ---------- | ----------- |
| **SNAKE** | Классика: поле 42×15, рост, ускорение, рекорд | стик, OK — рестарт |
| **TETRIS** | Фигуры 2×2, линии, счёт | стик ←→↓, OK — поворот |
| **2048** | Классика: слияния, счёт, рекорд | стик — ходы, OK — рестарт |
| **PONG** | Против CPU, счёт до 5 | стик ←→ |
| **SLOTS** | 3 барабана, честные частоты оригинала, 7 символов, джекпот 150 | OK — спин |
| **MINES** | Сапёр 14×7, 10 мин, первый клик безопасен, флаги (hold OK) | стик, OK, hold OK |
| **WIRES** | Соедини 4 провода: перестановка каждый раз | стик, OK |
| **SPINNER** | Колесо фортуны, 24 позиции, честный стоп | OK — спин |
| **COIN** | Монетка с анимацией | OK — бросок |
| **ROOTBEAR** | Медведь-бармен: налей ровно до метки (авторская) | стик, OK |
| **BUCKSHOT** | (авторская) | |
| **POUR** | Прототип Root Bear (авторская) | стик, OK |

## 🛠 Инструменты (tools/)

| Файл | Назначение |
| ------ | ----------- |
| `xlas.py` | Ассемблер: `.xlas` (текст) → `.xla` (байт-код) |
| `xla_sim.py` | **Симулятор VM на ПК** — отладка без железа, ASCII-экран |
| `xla_disasm.py` | Дизассемблер `.xla` |
| `gen_opcodes.py` | Таблица опкодов из ЕДИНОГО источника (заголовок прошивки) |
| `lint_xlas.py` | Проверка `.xlas` на неизвестные мнемоники |
| `test_tools.py` | Roundtrip-тесты (13/13) |

### Собрать и проверить игру без консоли

```bash
python tools/xlas.py apps/snake.xlas apps/snake.xla   # ассемблировать
python tools/lint_xlas.py apps/snake.xlas             # проверить
python - <<'EOF'                                      # симулятор: 100 кадров
from xla_sim import Sim
from pathlib import Path
sim = Sim(Path("apps/snake.xla").read_bytes())
for i in range(100): sim.step(0)
print(sim.stack)  # [] = чисто
EOF
```

## ✍️ Написать свою игру (5 минут)

`.xlas` — это стековый ассемблер. Смотри [`apps/coin.xlas`](apps/coin.xlas)
(самая простая, ~60 строк) и [`apps/snake.xlas`](apps/snake.xlas) (полная игра).

```asm
.title MYGAME          ; имя в каталоге (1..12 симв)
.data 32               ; 32 int16-глобалов
.str s_hi HELLO        ; строка в пуле

start:
    push 0
    gstore 0           ; g0 = счётчик

main:
    frame              ; конец кадра (60 fps)
    event              ; событие со стека: 5=OK 6=EXIT
    dup
    push 6
    eq
    jnz quit
    drop
    cls
    text 40 30 1 s_hi  ; вывести строку
    gload 0
    num 40 44 1        ; число
    disp
    jmp main

quit:
    drop
    exit
```

**Опкоды**: 69 шт., все — в [`src/xla_opcodes.h`](https://github.com/Olegu621/xlamper-firmware/blob/main/src/xla_opcodes.h)
прошивки. Ключевые: `push/dup/drop/swap`, `add/sub/mul/div/mod`,
`gstore/gload/gstorei/gloadi` (глобалы), `jmp/jz/jnz/call/ret`,
`frame/event/stick/hold` (ввод), `cls/px/line/rect/frect/circ/text/num/disp`
(экран), `beep/msec/rand/save/load` (прочее).

**Семантика (важно!)**:

- `GSTOREI` берёт стек `[v, idx]` — **значение пушится первым, индекс верхним**
- `RAND` берёт модуль со стека: `push 81; rand` → 0..80
- `JZ/JNZ` всегда снимают условие
- Графика берёт аргументы со стека: `rect 1 2 3 4 5` == 5 push + RECT

### Опубликовать

1. Форкни репозиторий
2. `apps/mygame.xla` + `apps/mygame.xlas` (исходник обязателен)
3. Строка в `manifest.txt`: `mygame|MYGAME|games`
4. PR! После мержа игра появится на всех консолях при следующем RESYNC

## 📡 Формат манифеста

```
файл|TITLE|категория
snake|SNAKE|games
```

Категории: `games`, `media`, `tools`. Файл — без расширения,
`.xla` добавляется прошивкой (`apps/<файл>.xla`).

---

<div align="center">

**Прошивка**: [Olegu621/xlamper-firmware](https://github.com/Olegu621/xlamper-firmware) ·
**Железо**: ESP32-C3 Super Mini + SSD1306 + стик + пьезо

*Сделано с 💜 и 69 опкодами*

</div>
