# Сценарный тест ROOT BEAR: полный игровой цикл + сохранение кадров
# Живёт в tools/ рядом с xla_sim.py — импорт резолвится статически.
from xla_sim import load


def read_bytes(path: str) -> bytes:
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except OSError as exc:
        raise SystemExit(f'cannot read {path}: {exc}') from exc


def write_text(path: str, text: str) -> None:
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    except OSError as exc:
        raise SystemExit(f'cannot write {path}: {exc}') from exc


def main() -> None:
    blob = read_bytes(r'..\apps\rootbear.xla')
    sim = load(blob)
    print(f'loaded {sim.title}: code={len(sim.code)} data={len(sim.data)} str={len(sim.strings)}')

    # сценарий: idle-кадры, клик(налив), налив, клик(подача), кадр оценки
    script = [0, 0, 0]          # заказ показан
    script += [5]               # клик -> налив
    script += [0] * 20          # налив
    script += [5]               # клик -> подача
    script += [0, 0]            # оценка висит
    script += [5]               # клик -> следующий клиент
    script += [0, 0]
    script += [5]               # налив снова
    script += [0] * 25          # дольше (до cap-защиты)
    script += [5]
    script += [0, 0]
    script += [6]               # exit

    saves = {
        2: r'..\dumps\rb_order.txt',
        23: r'..\dumps\rb_pour.txt',
        26: r'..\dumps\rb_grade.txt',
        60: r'..\dumps\rb_pour2.txt',
    }
    saved = 0
    try:
        for idx, ev in enumerate(script):
            r = sim.step(ev)
            if idx in saves:
                write_text(saves[idx], sim.disp.render())
                saved += 1
            if r == 3:
                print(f'EXIT at frame {idx}')
                break
            if r == 2:
                print(f'HALT at frame {idx}')
                break
    except Exception as exc:
        print(f'VM ERROR: {exc} @pc={sim.pc}', file=sys.stderr)
        sys.exit(1)

    print(f'saved {saved} frames, beeps: {sim.logs[-8:]}')
    print(f'nvs: {sim.nvs}')
    g = sim.data
    print(f'globals: fill={g[0]} foam={g[1]} score={g[4]} best={g[5]} state={g[6]} target={g[7]} streak={g[8]}')


if __name__ == '__main__':
    import os
    # рабочая директория = tools/ (где лежит скрипт), пути ../apps ../dumps
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    import sys
    try:
        main()
    except SystemExit as exc:
        print(f'FATAL: {exc}', file=sys.stderr)
        sys.exit(1)
