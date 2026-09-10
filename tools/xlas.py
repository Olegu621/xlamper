"""
xlas — ассемблер XLA-байткода для C3 XLAMPER.

Формат .xlas (простой текст, по одной инструкции на строку):
    ; комментарий
    .title POOR        ; имя плагина (1..12 симв, для NVS-ключей и заголовка)
    .data N           ; резервер N int16-глобалов (0..2048)
    .str NAME текст... ; именованная строка (в пул)
    label:            ; метка
    jmp label         ; безусловный переход
    jz label          ; если топ-стека == 0 (снимает значение)
    jnz label
    jeq label         ; флаговое сравнение не хранится, jz/jnz достаточно
    call label
    ret
    push 42
    pushstr NAME      ; кладёт offset строки в пул (число)
    px / line / rect / frect / circ / fcirc / ell — примитивы
    text size strNAME x y  ; порядок операндов — как в стеке: x y size str -> TEXT

Мнемоники соответствуют опкодам VM (см. c3_flipper.ino, секция XLA VM).
Порядок операндов стековый: инструкция укладывает аргументы так,
чтобы VM-опкод, сняв их со стека, получил правильный порядок.
Соглашение: значения на стеке кладутся в порядке «как пишутся».

Т.е. `px 10 20 1` кодирует: PUSH 10, PUSH 20, PUSH 1, PX
   (PX снимает c,y,x и рисует точку в (x,y) цветом c)
"""

import re
import struct
import sys
from dataclasses import dataclass, field

# --- опкоды (синхронизировано с c3_flipper.ino / XLA VM) ---
OP = {
    "halt": 0x00,
    "push": 0x01,
    "dup": 0x02,
    "drop": 0x03,
    "swap": 0x04,
    "over": 0x05,
    "pick": 0x06,
    "add": 0x20,
    "sub": 0x21,
    "mul": 0x22,
    "div": 0x23,
    "mod": 0x24,
    "neg": 0x25,
    "min": 0x26,
    "max": 0x27,
    "abs": 0x28,
    "eq": 0x30,
    "ne": 0x31,
    "lt": 0x32,
    "le": 0x33,
    "gt": 0x34,
    "ge": 0x35,
    "and": 0x36,
    "or": 0x37,
    "xor": 0x38,
    "not": 0x39,
    "gstore": 0x45,
    "gload": 0x46,
    "gstorei": 0x47,
    "gloadi": 0x48,
    "gcpy": 0x49,
    "jmp": 0x50,
    "jz": 0x51,
    "jnz": 0x52,
    "call": 0x53,
    "ret": 0x54,
    "frame": 0x5F,
    "px": 0x60,
    "line": 0x61,
    "rect": 0x62,
    "frect": 0x63,
    "circ": 0x64,
    "fcirc": 0x65,
    "ell": 0x66,
    "text": 0x67,
    "inv": 0x68,
    "fill": 0x69,
    "cls": 0x6A,
    "disp": 0x6B,
    "msec": 0x70,
    "rand": 0x71,
    "beep": 0x72,
    "exit": 0x73,
    "save": 0x74,
    "load": 0x75,
    "log": 0x76,
    "num": 0x77,
    "delay": 0x7A,
    "stx": 0x80,
    "sty": 0x81,
    "stick": 0x82,
    "event": 0x83,
    "hold": 0x84,
    "httpget": 0x78,  # strIdx imm16: URL из строк -> GET -> len|-1 на стек
    "httpch": 0x79,  # idx со стека: char ответа на стек
    "wget": 0x7B,  # dst cnt со стека: HTTP-ответ -> data-секция (int16), возвращает кол-во слов
    "sin": 0x90,
    "cos": 0x91,
    "sqrt": 0x92,
}

# мнемоники, требующие imm16-операнд (кроме push/pushstr — особые)
IMM16 = {"gstore", "gload", "httpget"}
# мнемоники со строковым операндом (строковый индекс)
STROPS = {"text", "save", "load", "httpget"}


class AsmError(Exception):
    pass


def _int_or_err(s: str, lineno: int, what: str) -> int:
    """int() с человеческой ошибкой вместо ValueError."""
    try:
        return int(s, 0)
    except ValueError:
        raise AsmError(f"{lineno}: {what} — не число: {s!r}") from None


@dataclass
class Line:
    src: str
    lineno: int
    op: str = ""
    args: list = field(default_factory=list)


@dataclass
class Program:
    title: str = "APP"
    data_slots: int = 0
    strings: dict = field(default_factory=dict)  # name -> bytes (без NUL)
    lines: list = field(default_factory=list)  # Line[]
    labels: dict = field(default_factory=dict)  # label -> code offset
    refs: list = field(default_factory=list)  # (lineno, code_off, label, size)


def parse(src: str) -> Program:
    prog = Program()
    for ln_no, raw in enumerate(src.splitlines(), 1):
        line = raw.split(";")[0].strip()
        if not line:
            continue
        if line.startswith("."):
            parts = line.split(None, 2)
            d = parts[0]
            if d == ".title":
                if len(parts) < 2 or not (1 <= len(parts[1]) <= 12):
                    raise AsmError(f"{ln_no}: .title требует 1..12 символов")
                prog.title = parts[1]
            elif d == ".data":
                if len(parts) < 2:
                    raise AsmError(f"{ln_no}: .data требует число 0..2048")
                n = _int_or_err(parts[1], ln_no, ".data")
                if not 0 <= n <= 2048:
                    raise AsmError(f"{ln_no}: .data 0..2048, получено {n}")
                prog.data_slots = n
            elif d == ".str":
                m = re.match(r"\.str\s+(\w+)\s+(.+)$", line)
                if not m:
                    raise AsmError(f"{ln_no}: .str ИМЯ текст")
                prog.strings[m.group(1)] = m.group(2).encode("utf-8")
            else:
                raise AsmError(f"{ln_no}: неизвестная директива {d}")
            continue
        if line.endswith(":"):
            prog.lines.append(Line(src=raw, lineno=ln_no, op=f"{line[:-1]}:"))
            continue
        parts = line.split()
        mnem = parts[0].lower()
        if mnem not in OP:
            raise AsmError(f"{ln_no}: неизвестная мнемоника {parts[0]}")
        prog.lines.append(Line(src=raw, lineno=ln_no, op=mnem, args=parts[1:]))
    return prog


def encode(prog: Program) -> bytes:
    code = bytearray()
    # first pass: encode with placeholders for label refs
    for ln in prog.lines:
        if ln.op.endswith(":"):
            prog.labels[ln.op[:-1]] = len(code)
            continue
        mnem = ln.op
        op = OP[mnem]
        args = ln.args
        if mnem == "push":
            if len(args) != 1:
                raise AsmError(f"{ln.lineno}: push IMM")
            v = _int_or_err(args[0], ln.lineno, "push")
            if not -32768 <= v <= 65535:
                raise AsmError(f"{ln.lineno}: push {v} вне int16")
            code += bytes([op]) + struct.pack("<h", v if v < 32768 else v - 65536)
        elif mnem == "pushstr":
            if len(args) != 1 or args[0] not in prog.strings:
                raise AsmError(f"{ln.lineno}: pushstr ИМЯ (строка не объявлена)")
            off = str_off(prog, args[0])
            code += bytes([OP["push"]]) + struct.pack("<h", off)
        elif mnem in IMM16:
            if len(args) != 1:
                raise AsmError(f"{ln.lineno}: {mnem} IDX (uint16)")
            idx = _int_or_err(args[0], ln.lineno, mnem)
            if not 0 <= idx <= 65535:
                raise AsmError(f"{ln.lineno}: {mnem} IDX 0..65535, получено {idx}")
            code += bytes([op]) + struct.pack("<H", idx)
        elif mnem in ("jmp", "jz", "jnz", "call"):
            if len(args) != 1:
                raise AsmError(f"{ln.lineno}: {mnem} LABEL")
            code += bytes([op])
            prog.refs.append((ln.lineno, len(code), args[0], 2))
            code += b"\x00\x00"
        elif mnem in STROPS:
            # text X Y SIZE STRNAME | save STRNAME V | load STRNAME DEF
            # кодируем: сначала push всех аргументов, потом опкод со строковым imm16
            # порядок: как в C-VM — опкод снимает в обратном порядке
            if mnem == "text":
                if len(args) != 4:
                    raise AsmError(f"{ln.lineno}: text X Y SIZE STRNAME")
                for a in args[:3]:
                    code += bytes([OP["push"]]) + struct.pack(
                        "<h", _int_or_err(a, ln.lineno, "text")
                    )
                code += bytes([op]) + struct.pack("<H", str_off(prog, args[3]))
            elif mnem == "save":
                # save STRNAME: значение уже на стеке (VM 0x74 снимает val, затем imm16)
                if len(args) != 1:
                    raise AsmError(f"{ln.lineno}: save STRNAME (значение на стеке)")
                code += bytes([op]) + struct.pack("<H", str_off(prog, args[0]))
            elif mnem == "load":
                # load STRNAME DEF: push DEF, затем опкод со imm16; результат на стеке
                if len(args) != 2:
                    raise AsmError(f"{ln.lineno}: load STRNAME DEF")
                code += bytes([OP["push"]]) + struct.pack(
                    "<h", _int_or_err(args[1], ln.lineno, "load")
                )
                code += bytes([op]) + struct.pack("<H", str_off(prog, args[0]))
        else:
            # стековые мнемоники: аргументы в строке (если есть) -> push,
            # затем сам опкод. Оба стиля допустимы:
            #   "rect 10 20 5 5 1"  ==  "push 10 / push 20 / ... / rect"
            # но НЕ одновременно (двойной push одного и того же значения).
            for a in args:
                code += bytes([OP["push"]]) + struct.pack(
                    "<h", _int_or_err(a, ln.lineno, mnem)
                )
            code += bytes([op])

    # second pass: patch label refs (rel16)
    for lineno, off, label, _sz in prog.refs:
        if label not in prog.labels:
            raise AsmError(f"{lineno}: метка {label} не определена")
        target = prog.labels[label]
        rel = target - (off + 2)  # rel от PC после операнда
        if not -32768 <= rel <= 32767:
            raise AsmError(f"{lineno}: rel16 слишком далеко: {rel}")
        struct.pack_into("<h", code, off, rel)

    return bytes(code)


# Все стековые опкоды — без аргументов в строке: параметры кладутся
# явными push-инструкциями. (NARGS пуст — зарезервировано)
NARGS = {}


def str_off(prog: Program, name: str) -> int:
    # офсет строки в пуле: строки укладываются последовательно, разделённые \0
    if name not in prog.strings:
        raise AsmError(f"строка {name} не объявлена")
    off = 0
    for nm, data in prog.strings.items():
        if nm == name:
            return off
        off += len(data) + 1
    raise AsmError(f"строка {name} не найдена в пуле")


def build_pool(prog: Program) -> bytes:
    pool = bytearray()
    for data in prog.strings.values():
        pool += data + b"\x00"
    return bytes(pool)


def assemble(src: str) -> bytes:
    prog = parse(src)
    code = encode(prog)
    pool = build_pool(prog)
    data = bytearray(prog.data_slots * 2)

    title = prog.title.encode("utf-8")[:12]
    hdr = bytearray()
    hdr += b"XLA1"  # magic
    hdr += bytes([1, 0])  # version, flags
    hdr += struct.pack("<H", len(code))
    hdr += struct.pack("<H", len(data))
    hdr += struct.pack("<H", len(pool))
    hdr += struct.pack("<H", 0)  # entry = 0
    hdr += struct.pack("<H", len(title))
    hdr += title
    blob = bytes(hdr) + code + bytes(data) + pool
    return blob


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python xlas.py input.xlas output.xla")
        sys.exit(2)
    src_path, out_path = sys.argv[1], sys.argv[2]
    try:
        with open(src_path, "rb") as fh:
            src = fh.read().decode("utf-8")
    except OSError as exc:
        print(f"cannot read {src_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        blob = assemble(src)
    except AsmError as exc:
        print(f"ASSEMBLY ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(out_path, "wb") as fh:
            fh.write(blob)
    except OSError as exc:
        print(f"cannot write {out_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"OK: {out_path} ({len(blob)} bytes) code={blob[6] | (blob[7] << 8)} "
        f"data={blob[8] | (blob[9] << 8)} str={blob[10] | (blob[11] << 8)} title={blob[16 : 16 + blob[14]]!r}"
    )


if __name__ == "__main__":
    main()
