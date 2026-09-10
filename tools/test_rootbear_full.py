# Полный жизненный цикл ROOTBEAR v2: боты с разными seed
import random
import sys

sys.path.insert(0, ".")
from xla_sim import load  # noqa: E402


def play(seed: int) -> tuple[bool, str]:
    random.seed(seed)
    with open(r"..\apps\rootbear.xla", "rb") as fh:
        sim = load(fh.read())
    steps = 0
    stuck = False
    while steps < 4200:
        g = sim.data
        if g[5] == 2:
            break
        if g[5] == 0:
            if g[2] == 0:
                sim.stick_y = random.choice([2500, 2900, 3300, 4095])
            else:
                eff = g[0] + g[1] // 4
                if eff >= g[6] - random.randint(0, 3) or g[0] > 90:
                    sim.stick_y = 2048
        sim.step(0)
        steps += 1
        if sim.data[5] == 1:
            w = 0
            while sim.data[10] > 0 and w < 300:
                sim.step(0)
                steps += 1
                w += 1
            if w >= 300:
                stuck = True
                break
    ok = sim.data[5] == 2 and not stuck and sim.stack == [] and 3500 <= steps <= 3750
    msg = (
        f"seed {seed}: steps={steps} money=${sim.data[3]} pours={sim.data[13]} "
        f"stuck={stuck} stack={sim.stack} nvs={sim.nvs} -> {'OK' if ok else 'FAIL'}"
    )
    return ok, msg


def main() -> None:
    all_ok = True
    for seed in (7, 99, 123, 2024):
        ok, msg = play(seed)
        all_ok = all_ok and ok
        print(msg)
    print("ALL PASS" if all_ok else "SOME FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
