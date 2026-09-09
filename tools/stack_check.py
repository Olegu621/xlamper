# Проверка стабильности стека для всех плагинов (10 idle-кадров)
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from xla_sim import load  # noqa: E402


def main() -> None:
    ok = True
    for name in ("rootbear", "pour"):
        try:
            with open(f"..\\apps\\{name}.xla", "rb") as fh:
                blob = fh.read()
        except OSError as exc:
            print(f"{name}: cannot read: {exc}")
            ok = False
            continue
        sim = load(blob)
        leaks = []
        for i in range(10):
            d0 = len(sim.stack)
            sim.step(0)
            if len(sim.stack) != d0:
                leaks.append((i, d0, len(sim.stack)))
        if leaks:
            print(f"{name}: STACK LEAK {leaks}")
            ok = False
        else:
            print(f"{name}: stack stable over 10 frames OK")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
