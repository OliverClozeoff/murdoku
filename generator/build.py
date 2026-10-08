"""Generate puzzles into docs/puzzles/ for the web game.

Usage:
    py generator/build.py                      # default set
    py generator/build.py --count 30 --seed 7  # custom
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from murdoku.generate import generate  # noqa: E402

# (size, difficulty) cycled through when building a set
PLAN = [(5, "easy"), (5, "medium"), (6, "easy"), (6, "medium"), (6, "hard"), (7, "medium"), (7, "hard"),
        (8, "hard"), (9, "expert")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=27, help="number of puzzles")
    ap.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same puzzles)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "docs" / "puzzles")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("*.json"):
        old.unlink()

    index = []
    for i in range(args.count):
        size, difficulty = PLAN[i % len(PLAN)]
        rng = random.Random(f"{args.seed}-{i}")
        t = time.perf_counter()
        puzzle = generate(size, difficulty, rng)
        pid = f"case-{i + 1:03d}"
        puzzle["id"] = pid
        puzzle["title"] = f"Case #{i + 1}"
        (args.out / f"{pid}.json").write_text(json.dumps(puzzle, ensure_ascii=False), encoding="utf-8")
        blocked = sorted({r * size + c for o in puzzle["objects"] if not o["occupiable"] for r, c in o["cells"]})
        index.append({"id": pid, "title": puzzle["title"], "size": size, "difficulty": difficulty,
                      "rooms": [r["name"] for r in puzzle["rooms"]],
                      # enough to draw the little floor-plan preview on the case list
                      "grid": puzzle["grid"], "colors": [r["color"] for r in puzzle["rooms"]], "blocked": blocked})
        print(f"{pid}: {size}x{size} {difficulty:<6} steps={puzzle['stats']}  {time.perf_counter() - t:.1f}s")

    (args.out / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(index)} puzzles to {args.out}")


if __name__ == "__main__":
    main()
