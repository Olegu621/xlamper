# Дизассемблер .xla — показ кода в удобочитаемом виде (для отладки)
import sys

OPN = {0x00: 'HALT', 0x01: 'PUSH', 0x02: 'DUP', 0x03: 'DROP', 0x04: 'SWAP', 0x05: 'OVER', 0x06: 'PICK',
       0x20: 'ADD', 0x21: 'SUB', 0x22: 'MUL', 0x23: 'DIV', 0x24: 'MOD', 0x25: 'NEG', 0x26: 'MIN', 0x27: 'MAX', 0x28: 'ABS',
       0x30: 'EQ', 0x31: 'NE', 0x32: 'LT', 0x33: 'LE', 0x34: 'GT', 0x35: 'GE', 0x36: 'AND', 0x37: 'OR', 0x38: 'XOR', 0x39: 'NOT',
       0x45: 'GSTORE', 0x46: 'GLOAD', 0x47: 'GSTOREI', 0x48: 'GLOADI',
       0x50: 'JMP', 0x51: 'JZ', 0x52: 'JNZ', 0x53: 'CALL', 0x54: 'RET', 0x5F: 'FRAME',
       0x60: 'PX', 0x61: 'LINE', 0x62: 'RECT', 0x63: 'FRECT', 0x64: 'CIRC', 0x65: 'FCIRC', 0x66: 'ELL', 0x67: 'TEXT',
       0x68: 'INV', 0x69: 'FILL', 0x6A: 'CLS', 0x6B: 'DISP',
       0x70: 'MSEC', 0x71: 'RAND', 0x72: 'BEEP', 0x73: 'EXIT', 0x74: 'SAVE', 0x75: 'LOAD', 0x76: 'LOG', 0x77: 'NUM',
       0x80: 'STX', 0x81: 'STY', 0x82: 'STICK', 0x83: 'EVENT', 0x84: 'HOLD',
       0x90: 'SIN', 0x91: 'COS', 0x92: 'SQRT'}
IMM = {0x01, 0x45, 0x46, 0x50, 0x51, 0x52, 0x53, 0x67, 0x74, 0x75}


def _parse_range(rng: str, code_len: int):
    """Парсит диапазон 'from..to' / '@pc' / 'pc'; возвращает (lo, hi)."""
    try:
        if rng.startswith('@'):
            c = int(rng[1:])
            return max(0, c - 20), min(code_len, c + 20)
        if '..' in rng:
            a, b = rng.split('..')
            return int(a), int(b)
        if rng.isdigit():
            c = int(rng)
            return max(0, c - 20), min(code_len, c + 20)
    except ValueError:
        print(f'bad range {rng!r}, dumping all', file=sys.stderr)
    return 0, code_len


def main() -> None:
    if len(sys.argv) < 3:
        print('usage: python xla_disasm.py app.xla [from..to | @pc]')
        sys.exit(2)
    try:
        with open(sys.argv[1], 'rb') as fh:
            blob = fh.read()
    except OSError as exc:
        print(f'cannot read: {exc}', file=sys.stderr)
        sys.exit(1)
    code_sz = blob[6] | (blob[7] << 8)
    tl = blob[14] | (blob[15] << 8)
    p = 16 + tl
    code = blob[p:p + code_sz]
    rng = sys.argv[2]
    lo, hi = _parse_range(rng, len(code))
    pc = 0
    while pc < len(code):
        start = pc
        op = code[pc]
        name = OPN.get(op, f'?{op:02X}')
        if op in IMM:
            v = code[pc + 1] | (code[pc + 2] << 8)
            sv = v - 65536 if v >= 32768 else v
            if lo <= start <= hi:
                print(f'pc={start:4d}: {name} {sv}')
            pc += 3
        else:
            if lo <= start <= hi:
                print(f'pc={start:4d}: {name}')
            pc += 1


if __name__ == '__main__':
    main()
