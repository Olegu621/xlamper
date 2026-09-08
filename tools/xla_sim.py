"""
xla_sim — симулятор XLA VM (C3 XLAMPER) на Python.
Точная копия семантики VM из c3_flipper.ino (v1).
Рисует в ASCII-канвас 128x64, события подаются скриптом.
Использование: для отладки плагинов до заливки в железо.
"""
import math
import struct
import sys
import time
from dataclasses import dataclass, field

W, H = 128, 64
STACK_MAX = 96
RET_MAX = 16
FRAME_INSN = 6000
MAXCODE, MAXDATA, MAXSTR = 20000, 4096, 8000
TITLELEN = 12

HALT, FRAME, EXIT = 2, 1, 3


class VMError(Exception):
    pass


def _safe_int(v) -> int:
    """int() без исключений: конечная арифметика не падает,
    но все точки конверсии обёрнуты единообразно."""
    try:
        return int(v)
    except (ValueError, OverflowError):
        return 0


@dataclass
class Display:
    px: list = field(default_factory=lambda: [[0] * W for _ in range(H)])
    cx: int = 0
    cy: int = 0
    size: int = 1

    def clear(self):
        self.px = [[0] * W for _ in range(H)]

    def setpixel(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.px[y][x] = 1 if c else 0

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.setpixel(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def rect(self, x, y, w, h, c, fill):
        if w <= 0 or h <= 0:
            return
        if fill:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    self.setpixel(xx, yy, c)
        else:
            self.line(x, y, x + w - 1, y, c)
            self.line(x, y + h - 1, x + w - 1, y + h - 1, c)
            self.line(x, y, x, y + h - 1, c)
            self.line(x + w - 1, y, x + w - 1, y + h - 1, c)

    def disc(self, cx, cy, r, c):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.setpixel(x, y, c)

    def ellipse_fill(self, cx, cy, rx, ry, c):
        if rx <= 0 or ry <= 0:
            self.disc(cx, cy, max(rx, 1), c)
            return
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.setpixel(x, y, c)

    def render(self) -> str:
        """Точный рендер 1:1 — по строкам (64 строки по 128 символов)."""
        return '\n'.join(
            ''.join('#' if self.px[y][x] else '.' for x in range(W))
            for y in range(H)
        )

    def render_half(self) -> str:
        """Сжатый рендер: 32 строки (пары пиксельных строк через OR)."""
        rows = []
        for band in range(0, H, 2):
            rows.append(''.join(
                '#' if (self.px[band][x] or self.px[band + 1][x]) else '.'
                for x in range(W)))
        return '\n'.join(rows)


@dataclass
class Sim:
    code: bytes
    data: list
    strings: bytes
    entry: int
    title: str
    disp: Display = field(default_factory=Display)
    pc: int = 0
    sp: int = 0
    stack: list = field(default_factory=list)
    ret: list = field(default_factory=list)
    running: bool = True
    err: str = ''
    ev: int = 0            # текущее событие (кадр)
    nvs: dict = field(default_factory=dict)
    t0: float = field(default_factory=time.monotonic)
    frames: int = 0
    budget_used: int = 0
    logs: list = field(default_factory=list)

    # ---- fetch ----
    def f8(self):
        if self.pc >= len(self.code):
            raise VMError('PC OOB')
        b = self.code[self.pc]
        self.pc += 1
        return b

    def f16(self):
        lo = self.f8()
        hi = self.f8()
        return (hi << 8) | lo

    def s16(self):
        v = self.f16()
        return v - 65536 if v >= 32768 else v

    def str_at(self, off):
        if off >= len(self.strings):
            raise VMError('str OOB')
        end = self.strings.index(b'\x00', off)
        return self.strings[off:end].decode('utf-8', 'replace')

    def push(self, v):
        if len(self.stack) >= STACK_MAX:
            raise VMError('stack ovf')
        self.stack.append(v)

    def pop(self):
        if not self.stack:
            raise VMError('stack und')
        return self.stack.pop()

    def msec(self):
        try:
            return int((time.monotonic() - self.t0) * 1000) & 0x7FFF
        except OSError:
            return 0

    def key(self, k):
        return f'{self.title}_{k}'

    # один кадр; ev: 0 none, 1 up, 2 down, 3 left, 4 right, 5 ok, 6 exit
    def step(self, ev: int = 0) -> int:
        self.ev = ev
        budget = FRAME_INSN
        while budget:
            budget -= 1
            op = self.f8()
            if op == 0x00:
                return HALT
            elif op == 0x01:
                self.push(self.s16())
            elif op == 0x02:
                v = self.pop()
                self.push(v)
                self.push(v)
            elif op == 0x03:
                self.pop()
            elif op == 0x04:
                b, a = self.pop(), self.pop()
                self.push(b)
                self.push(a)
            elif op == 0x05:
                b, a = self.pop(), self.pop()
                self.push(a)
                self.push(b)
                self.push(a)
            elif op == 0x06:
                n = self.pop()
                i = len(self.stack) - 1 - n
                self.push(self.stack[i] if 0 <= i < len(self.stack) else 0)
            elif op == 0x20:
                b, a = self.pop(), self.pop()
                self.push(_w(a + b))
            elif op == 0x21:
                b, a = self.pop(), self.pop()
                self.push(_w(a - b))
            elif op == 0x22:
                b, a = self.pop(), self.pop()
                self.push(_w(a * b))
            elif op == 0x23:
                b, a = self.pop(), self.pop()
                if b == 0:
                    raise VMError('div0')
                self.push(_w(_safe_int(a / b)))     # C-style trunc div
            elif op == 0x24:
                b, a = self.pop(), self.pop()
                if b == 0:
                    raise VMError('mod0')
                self.push(_w(a - _safe_int(a / b) * b))   # C-style trunc mod
            elif op == 0x25:
                self.push(_w(-self.pop()))
            elif op == 0x26:
                b, a = self.pop(), self.pop()
                self.push(min(a, b))
            elif op == 0x27:
                b, a = self.pop(), self.pop()
                self.push(max(a, b))
            elif op == 0x28:
                a = self.pop()
                self.push(abs(a))
            elif op == 0x30:
                b, a = self.pop(), self.pop()
                self.push(1 if a == b else 0)
            elif op == 0x31:
                b, a = self.pop(), self.pop()
                self.push(1 if a != b else 0)
            elif op == 0x32:
                b, a = self.pop(), self.pop()
                self.push(1 if a < b else 0)
            elif op == 0x33:
                b, a = self.pop(), self.pop()
                self.push(1 if a <= b else 0)
            elif op == 0x34:
                b, a = self.pop(), self.pop()
                self.push(1 if a > b else 0)
            elif op == 0x35:
                b, a = self.pop(), self.pop()
                self.push(1 if a >= b else 0)
            elif op == 0x36:
                b, a = self.pop(), self.pop()
                self.push(1 if (a != 0 and b != 0) else 0)
            elif op == 0x37:
                b, a = self.pop(), self.pop()
                self.push(1 if (a != 0 or b != 0) else 0)
            elif op == 0x38:
                b, a = self.pop(), self.pop()
                self.push(1 if (a != 0) != (b != 0) else 0)
            elif op == 0x39:
                self.push(1 if self.pop() == 0 else 0)
            elif op == 0x45:
                idx = self.f16()
                v = self.pop()
                if idx >= len(self.data):
                    raise VMError('g OOB')
                self.data[idx] = v
            elif op == 0x46:
                idx = self.f16()
                if idx >= len(self.data):
                    raise VMError('g OOB')
                self.push(self.data[idx])
            elif op == 0x47:
                idx = self.pop()
                v = self.pop()
                if idx < 0 or idx >= len(self.data):
                    raise VMError('g OOB')
                self.data[idx] = v
            elif op == 0x48:
                idx = self.pop()
                if idx < 0 or idx >= len(self.data):
                    raise VMError('g OOB')
                self.push(self.data[idx])
            elif op == 0x50:
                rel = self.s16()
                self.pc = _w(self.pc + rel) & 0xFFFF
            elif op == 0x51:
                rel = self.s16()
                if self.pop() == 0:
                    self.pc = _w(self.pc + rel) & 0xFFFF
            elif op == 0x52:
                rel = self.s16()
                if self.pop() != 0:
                    self.pc = _w(self.pc + rel) & 0xFFFF
            elif op == 0x53:
                rel = self.s16()
                if len(self.ret) >= RET_MAX:
                    raise VMError('ret ovf')
                self.ret.append(self.pc)
                self.pc = _w(self.pc + rel) & 0xFFFF
            elif op == 0x54:
                if not self.ret:
                    raise VMError('ret und')
                self.pc = self.ret.pop()
            elif op == 0x5F:
                return FRAME
            elif op == 0x60:
                c, y, x = self.pop(), self.pop(), self.pop()
                self.disp.setpixel(x, y, c)
            elif op == 0x61:
                c, y1, x1, y0, x0 = self.pop(), self.pop(), self.pop(), self.pop(), self.pop()
                self.disp.line(x0, y0, x1, y1, c)
            elif op == 0x62:
                c, h, w, y, x = self.pop(), self.pop(), self.pop(), self.pop(), self.pop()
                self.disp.rect(x, y, w, h, c, fill=False)
            elif op == 0x63:
                c, h, w, y, x = self.pop(), self.pop(), self.pop(), self.pop(), self.pop()
                self.disp.rect(x, y, w, h, c, fill=True)
            elif op == 0x64:
                c, r, y, x = self.pop(), self.pop(), self.pop(), self.pop()
                # окружность — по пикселям
                for a in range(0, 360, 2):
                    rad = math.radians(a)
                    self.disp.setpixel(_safe_int(x + r * math.cos(rad)), _safe_int(y + r * math.sin(rad)), c)
            elif op == 0x65:
                c, r, y, x = self.pop(), self.pop(), self.pop(), self.pop()
                self.disp.disc(x, y, r, c)
            elif op == 0x66:
                c, ry, rx, y, x = self.pop(), self.pop(), self.pop(), self.pop(), self.pop()
                self.disp.ellipse_fill(x, y, rx, ry, c)
            elif op == 0x67:
                off = self.f16()
                f, y, x = self.pop(), self.pop(), self.pop()
                s = self.str_at(off)
                self.disp.cx, self.disp.cy, self.disp.size = x, y, f
                self._text(s)
            elif op == 0x68:
                pass  # invert flash — в симе просто мигнуть
            elif op == 0x69:
                c = self.pop()
                self.disp.rect(0, 0, W, H, c, fill=True)
            elif op == 0x6A:
                self.disp.clear()
            elif op == 0x6B:
                self.frames += 1
            elif op == 0x70:
                self.push(self.msec() & 0x7FFF)
            elif op == 0x71:
                m = self.pop()
                self.push(0 if m <= 0 else int.from_bytes(struct.pack('<I', _w(m)), 'little') % m)
            elif op == 0x72:
                ms, f = self.pop(), self.pop()
                # beep в симуляторе — печать
                self.logs.append(f'beep({f},{ms})')
            elif op == 0x73:
                return EXIT
            elif op == 0x74:
                koff = self.f16()
                v = self.pop()
                self.nvs[self.key(self.str_at(koff))] = v
            elif op == 0x75:
                koff = self.f16()
                d = self.pop()
                self.push(self.nvs.get(self.key(self.str_at(koff)), d))
            elif op == 0x76:
                v = self.pop()
                self.logs.append(f'log({v})')
            elif op == 0x77:
                v = self.pop()
                f = self.pop()
                y = self.pop()
                x = self.pop()
                self.disp.cx, self.disp.cy, self.disp.size = x, y, f
                self._text(str(v))
            elif op == 0x80:
                self.push(0)   # stx центр
            elif op == 0x81:
                self.push(0)
            elif op == 0x82:
                # стик: маппинг события -> 8-way (0 up, 2 right, 4 down, 6 left); idle -> -1
                evmap = {1: 0, 2: 4, 3: 6, 4: 2}   # ev: 1 up, 2 down, 3 left, 4 right
                self.push(evmap.get(self.ev, -1))
            elif op == 0x83:
                self.push(self.ev)
            elif op == 0x84:
                self.push(0)
            elif op == 0x90:
                a = self.pop()
                self.push(_safe_int(math.sin(math.radians(a)) * 1000))
            elif op == 0x91:
                a = self.pop()
                self.push(_safe_int(math.cos(math.radians(a)) * 1000))
            elif op == 0x92:
                v = self.pop()
                self.push(0 if v <= 0 else _safe_int(math.sqrt(v) + 0.5))
            else:
                raise VMError(f'bad op {op:02X} @pc={self.pc - 1}')
        return 0

    def _text(self, s: str) -> None:
        # крошечный 3x5 ASCII для симуляции
        FONT = {
            'A': ['010', '101', '111', '101', '101'], 'B': ['110', '101', '110', '101', '110'],
            'C': ['011', '100', '100', '100', '011'], 'D': ['110', '101', '101', '101', '110'],
            'E': ['111', '100', '110', '100', '111'], 'F': ['111', '100', '110', '100', '100'],
            'G': ['011', '100', '101', '101', '011'], 'H': ['101', '101', '111', '101', '101'],
            'I': ['111', '010', '010', '010', '111'], 'J': ['001', '001', '001', '101', '011'],
            'K': ['101', '101', '110', '101', '101'], 'L': ['100', '100', '100', '100', '111'],
            'M': ['101', '111', '111', '101', '101'], 'N': ['110', '101', '101', '101', '101'],
            'O': ['010', '101', '101', '101', '010'], 'P': ['110', '101', '110', '100', '100'],
            'Q': ['010', '101', '101', '111', '011'], 'R': ['110', '101', '110', '101', '101'],
            'S': ['011', '100', '010', '001', '110'], 'T': ['111', '010', '010', '010', '010'],
            'U': ['101', '101', '101', '101', '111'], 'V': ['101', '101', '101', '101', '010'],
            'W': ['101', '101', '111', '111', '101'], 'X': ['101', '101', '010', '101', '101'],
            'Y': ['101', '101', '010', '010', '010'], 'Z': ['111', '001', '010', '100', '111'],
            '0': ['111', '101', '101', '101', '111'], '1': ['010', '110', '010', '010', '111'],
            '2': ['111', '001', '111', '100', '111'], '3': ['111', '001', '011', '001', '111'],
            '4': ['101', '101', '111', '001', '001'], '5': ['111', '100', '111', '001', '111'],
            '6': ['111', '100', '111', '101', '111'], '7': ['111', '001', '001', '010', '010'],
            '8': ['111', '101', '111', '101', '111'], '9': ['111', '101', '111', '001', '111'],
            '!': ['1', '1', '1', '0', '1'], '.': ['0', '0', '0', '0', '1'],
            ':': ['0', '1', '0', '1', '0'], ' ': ['0', '0', '0', '0', '0'],
            '=': ['0', '0', '1', '0', '1'], '/': ['0', '0', '0', '0', '0'],
            '-': ['0', '0', '0', '0', '0'], '>': ['0', '0', '0', '0', '0'],
        }
        x, y = self.disp.cx, self.disp.cy
        scale = max(1, self.disp.size * 4)
        for ch in s.upper():
            glyph = FONT.get(ch, FONT[' '])
            for gy, row in enumerate(glyph):
                if len(row) == 1:
                    cols = [row]
                else:
                    cols = row
                for gx, c in enumerate(cols):
                    if c == '1':
                        if scale == 1:
                            self.disp.setpixel(x + gx, y + gy, 1)
                        else:
                            self.disp.rect(x + gx * scale, y + gy * scale, scale, scale, 1, fill=True)
            x += (max(len(r) for r in glyph) + 1) * (scale // 4 if scale > 1 else 1) + 1


def _w(v: int) -> int:
    v &= 0xFFFF
    return v - 65536 if v >= 32768 else v


def load(blob: bytes) -> Sim:
    if len(blob) < 18 or blob[:4] != b'XLA1' or blob[4] != 1:
        raise VMError('bad header')
    code_sz = blob[6] | (blob[7] << 8)
    data_sz = blob[8] | (blob[9] << 8)
    str_sz = blob[10] | (blob[11] << 8)
    entry = blob[12] | (blob[13] << 8)
    tl = blob[14] | (blob[15] << 8)
    if tl == 0 or tl > TITLELEN:
        raise VMError('bad title len')
    p = 16
    title = blob[p:p + tl].decode()
    p += tl
    code = blob[p:p + code_sz]
    p += code_sz
    data_raw = blob[p:p + data_sz]
    p += data_sz
    strings = blob[p:p + str_sz]
    if len(code) != code_sz or len(data_raw) != data_sz or len(strings) != str_sz:
        raise VMError('truncated')
    data = list(struct.unpack(f'<{data_sz // 2}h', data_raw)) if data_sz else []
    if data_sz % 2:
        raise VMError('odd data size')
    return Sim(code=code, data=data, strings=strings, entry=entry, title=title)


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: python xla_sim.py app.xla [--script events]')
        sys.exit(2)
    try:
        with open(sys.argv[1], 'rb') as fh:
            blob = fh.read()
        sim = load(blob)
    except OSError as exc:
        print(f'cannot read {sys.argv[1]}: {exc}', file=sys.stderr)
        sys.exit(1)
    except VMError as exc:
        print(f'bad xla: {exc}', file=sys.stderr)
        sys.exit(1)
    print(f'loaded {sim.title}: code={len(sim.code)} data={len(sim.data)} str={len(sim.strings)}')
    # сценарий: 3 кадра idle, потом 20 кадров налива, клик-подача, 3 кадра
    script = [0, 0, 0, 5] + [0] * 40 + [5] + [0] * 3 + [6]
    try:
        for ev in script:
            r = sim.step(ev)
            if r == HALT:
                print('HALT')
                break
            if r == EXIT:
                print('EXIT')
                break
            if sim.frames % 10 == 0:
                print(f'--- frame {sim.frames} (pc={sim.pc}, sp={len(sim.stack)}) ---')
                print(sim.disp.render())
    except VMError as exc:
        print(f'VM ERROR: {exc} @pc={sim.pc}', file=sys.stderr)
        sys.exit(1)
    print(f'done: frames={sim.frames}, stack={sim.stack}, nvs={sim.nvs}')
    print(sim.disp.render())
    for line in sim.logs[-20:]:
        print('log:', line)


if __name__ == '__main__':
    main()
