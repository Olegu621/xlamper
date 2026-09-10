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
        scale = min(46 / w, 40 / h)
        tw, th = max(1, round(w * scale)), max(1, round(h * scale))
        ox = (46 - tw) // 2
        sub0 = pdi2xla.resize_px(px0, w, h, tw, th)

        def sub(x: int, y: int, _s=sub0) -> int:
            return 1 - _s(x, y)  # инверсия: белый силуэт медведя

        merged = pdi2xla.rows_to_frects(sub, tw, th)
        out.append(f"{name}:")
        for x, y, wd, ht in merged:
            out += [f"    push {x + ox}", f"    push {y + 4}", f"    push {wd}", f"    push {ht}", "    push 1", "    frect"]
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
