# Генератор RootBear v2: медведи + 4 типа стаканов (+overflow) -> spr_v2.xlas
# Выводит ASCII-рендер стаканов для подбора внутренних зон жидкости.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pdi2xla  # noqa: E402

PDX = Path(r"C:\Users\admin\Desktop\RootBear.pdx\images")
OUT = Path(r"C:\Users\admin\flipper\dumps\spr_v2.xlas")

# (тип, pdi-префикс glasses/NN_, целевой размер, широкая?)
GLASSES = [
    ("G0", "glasses/01_def_outline.pdi", 27, 40),  # тумблер
    ("G1", "glasses/02_hb_outline.pdi", 18, 41),   # хайбол (узкий высокий)
    ("G2", "glasses/03_whiskey_outline.pdi", 42, 36),  # шот/виски (низкий широкий)
    ("G3", "glasses/04_pitcher_outline.pdi", 29, 41),  # питчер (большой)
]
OVERFLOWS = [
    ("O0", "glasses/01_def_overflow.pdi", 27, 40),
    ("O1", "glasses/02_hb_overflow.pdi", 18, 41),
    ("O2", "glasses/03_whiskey_overflow.pdi", 42, 36),
    ("O3", "glasses/04_pitcher_overflow.pdi", 29, 41),
]


def conv(pdi: str, name: str, tw: int, th: int) -> tuple[list[str], list[list[int]]]:
    raw, w, h = pdi2xla.load_pdi(str(PDX / pdi))
    off = pdi2xla.find_bitmap_offset(raw, w, h)
    px = pdi2xla.get_px(raw, w, h, off)
    sub = pdi2xla.resize_px(px, w, h, tw, th)
    merged = pdi2xla.rows_to_frects(sub, tw, th)
    lines = [f"{name}:"]
    for x, y, wd, ht in merged:
        lines += [f"    push {x}", f"    push {y}", f"    push {wd}", f"    push {ht}", "    push 1", "    frect"]
    lines.append("    ret")
    bmp = [[1 if sub(x, y) else 0 for x in range(tw)] for y in range(th)]
    return lines, bmp


def render(bmp: list[list[int]]) -> str:
    return "\n".join("".join("#" if v else "." for v in row) for row in bmp)


def outline_px(px, w0: int, h0: int, invert: bool = True):
    """Контуры (line-art) из маски: пиксель = 1, если он в маске,
    но у него есть сосед вне маски (внутри 2px от края).
    invert=True: маска залита (медведь тёмный) -> контур белый + тёмные
    внутренние детали (глаза/рот) остаются тёмными = рисуем контур белым,
    детали потом инвертируем в отдельный проход."""

    def mask(x: int, y: int) -> int:
        return 1 if 0 <= x < w0 and 0 <= y < h0 and px(x, y) else 0

    def out(x: int, y: int) -> int:
        if not mask(x, y):
            return 0
        # край? сосед (включая диагонали) вне маски
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if not mask(x + dx, y + dy):
                    return 1
        return 0

    return out


def detail_px(px, w0: int, h0: int):
    """Внутренние тёмные детали (глаза/нос/рот): пиксель маски, окружённый
    маской со всех 4 сторон на расстоянии 1..2 (не край)."""

    def mask(x: int, y: int) -> int:
        return 1 if 0 <= x < w0 and 0 <= y < h0 and px(x, y) else 0

    def out(x: int, y: int) -> int:
        if not mask(x, y):
            return 0
        # не край
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if not mask(x + dx, y + dy):
                    return 0
        # но рядом (2px) есть дырка (глаз/рот)
        for dy in (-2, -1, 0, 1, 2):
            for dx in (-2, -1, 0, 1, 2):
                if not mask(x + dx, y + dy):
                    return 1
        return 0

    return out


def main() -> None:
    out: list[str] = []
    bears = [
        ("draw_b_neutral", "bears/bear_neutral.pdi"),
        ("draw_b_blink", "bears/bear_blink.pdi"),
        ("draw_b_nervous1", "bears/bear_nervous1.pdi"),
        ("draw_b_nervous2", "bears/bear_nervous2.pdi"),
        ("draw_b_good", "bears/bear_good.pdi"),
        ("draw_b_meh", "bears/bear_meh.pdi"),
        ("draw_b_perfect", "bears/bear_perfect.pdi"),
        ("draw_b_rage", "bears/bear_rage.pdi"),
    ]
    for name, pdi in bears:
        raw, w, h = pdi2xla.load_pdi(str(PDX / pdi))
        off = pdi2xla.find_bitmap_offset(raw, w, h)
        px0 = pdi2xla.get_px(raw, w, h, off)
        scale = min(46 / w, 44 / h)
        tw, th = max(1, round(w * scale)), max(1, round(h * scale))
        ox = (46 - tw) // 2
        sub0 = pdi2xla.resize_px(px0, w, h, tw, th)

        # LINE-ART: контур силуэта + внутренние детали (глаза/рот).
        # Белым рисуем пиксели медведя, у которых в соседях (8) есть дырку:
        # это и внешний контур, и границы глаз/рта — читаемое лицо на чёрном.
        def maskv(x: int, y: int, _s=sub0, _w=tw, _h=th) -> int:
            return 1 if 0 <= x < _w and 0 <= y < _h and _s(x, y) else 0

        edge_set: set[tuple[int, int]] = set()
        for y in range(th):
            for x in range(tw):
                if not maskv(x, y):
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if not maskv(x + dx, y + dy):
                            edge_set.add((x, y))
                            break
                    else:
                        continue
                    break

        def line_art(x: int, y: int, _e=edge_set) -> int:
            return 1 if (x, y) in _e else 0

        merged = pdi2xla.rows_to_frects(line_art, tw, th)
        out.append(f"{name}:")
        for x, y, wd, ht in merged:
            out += [f"    push {x + ox}", f"    push {y + 2}", f"    push {wd}", f"    push {ht}", "    push 1", "    frect"]
        out.append("    ret")

    dbg = Path(r"C:\Users\admin\flipper\dumps\glass_debug.txt")
    with dbg.open("w", encoding="utf-8") as fh:
        for tag, pdi, tw, th in GLASSES + OVERFLOWS:
            lines, bmp = conv(pdi, f"draw_{tag}", tw, th)
            out += lines
            fh.write(f"== {tag} {pdi} {tw}x{th} ==\n{render(bmp)}\n\n")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    n = sum(1 for ln in out if "frect" in ln)
    print(f"{OUT}: {n} frects = ~{n * 16} bytes")
    print(f"glass renders -> {dbg}")


if __name__ == "__main__":
    main()
