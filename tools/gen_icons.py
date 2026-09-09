# Генератор иконок для манифеста CLOUD (24 точки, сетка 40x38)
# Пары координат -> hex (4 символа на точку: XXYY)
import math


def icon_snake():
    pts = []
    # волнистая змейка с головой
    body = [
        (4, 24),
        (7, 22),
        (10, 20),
        (13, 22),
        (16, 24),
        (19, 26),
        (22, 28),
        (25, 30),
        (28, 28),
        (31, 26),
    ]
    for x, y in body:
        pts.append((x, y))
        pts.append((x, y + 3))
        pts.append((x + 2, y + 2))
    # глаз
    pts.append((34, 24))
    return pts


def icon_tetris():
    pts = []
    # стакан
    for y in range(4, 34, 2):
        pts.append((6, y))
        pts.append((30, y))
    for x in range(6, 31, 2):
        pts.append((x, 34))
    # I-фигура
    for x in (12, 14, 16, 18, 20):
        pts.append((x, 14))
        pts.append((x, 15))
    # O-фигура
    for x in (14, 16):
        for y in (20, 22):
            pts.append((x, y))
    return pts


def icon_2048():
    pts = []
    for x0, y0 in ((6, 6), (22, 6), (6, 22), (22, 22)):
        for x in range(x0, x0 + 12, 2):
            pts.append((x, y0))
            pts.append((x, y0 + 10))
        for y in range(y0, y0 + 10, 2):
            pts.append((x0, y))
            pts.append((x0 + 12, y))
    return pts


def icon_pong():
    pts = []
    # ракетки
    for y in (10, 12, 14, 16, 18):
        pts.append((8, y))
        pts.append((31, y))
    # мяч
    pts.append((20, 22))
    pts.append((21, 22))
    pts.append((20, 23))
    pts.append((21, 23))
    # разделительная
    for y in range(4, 34, 3):
        pts.append((19, y))
        pts.append((20, y))
    return pts


def icon_cube():
    pts = []
    s = 8
    a = [(8 + s, 4 + s), (24 - s, 4 + s), (24 - s, 20 - s), (8 + s, 20 - s)]
    b = [(4 + s, 8 + s), (28 - s, 8 + s), (28 - s, 24 - s), (4 + s, 24 - s)]
    pts.extend(a)
    pts.extend(b)
    for i in range(4):
        x0, y0 = a[i]
        x1, y1 = b[i]
        for t in (0, 4, 8):
            pts.append((x0 + (x1 - x0) * t // 8, y0 + (y1 - y0) * t // 8))
    return pts


def icon_pour():
    pts = []
    # кружка
    for y in range(16, 32, 2):
        pts.append((8, y))
        pts.append((26, y))
    for x in range(8, 27, 2):
        pts.append((x, 32))
        pts.append((x, 16))
    # ручка
    for x in range(28, 34, 2):
        pts.append((x, 20))
        pts.append((x, 27))
    # пена
    for x, y in ((10, 14), (13, 13), (16, 14), (19, 13), (22, 14)):
        pts.append((x, y))
    return pts


def icon_rootbear():
    pts = []
    # голова
    for a_deg in range(0, 360, 24):
        r = 7
        x = 14 + r * math.cos(math.radians(a_deg))
        y = 14 + r * math.sin(math.radians(a_deg))
        pts.append((int(x), int(y)))
    # уши
    pts.append((8, 7))
    pts.append((9, 6))
    pts.append((19, 6))
    pts.append((20, 7))
    # кружка
    for y in range(24, 34, 2):
        pts.append((28, y))
        pts.append((37, y))
    for x in range(28, 38, 2):
        pts.append((x, 34))
    return pts


ICONS = {
    "snake": icon_snake,
    "tetris": icon_tetris,
    "2048": icon_2048,
    "pong": icon_pong,
    "cube": icon_cube,
    "pour": icon_pour,
    "rootbear": icon_rootbear,
}


def pts_to_hex(pts, cap=40):
    pts = pts[:cap]
    return "".join(f"{x:02X}{y:02X}" for x, y in pts)


def main():
    for name, fn in ICONS.items():
        pts = fn()
        hexs = pts_to_hex(pts)
        print(f"{name}: {len(pts)} pts -> {len(hexs)} hex chars")


if __name__ == "__main__":
    main()
