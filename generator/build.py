"""Generate puzzles into docs/puzzles/ for the web game.

Usage:
    py generator/build.py                      # default set
    py generator/build.py --count 30 --seed 7  # custom
    py generator/build.py --reorder            # renumber the existing set (easy -> expert), no regenerating
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from murdoku.generate import generate  # noqa: E402

# (size, difficulty) cycled through when building a set
PLAN = [(5, "easy"), (5, "medium"), (6, "easy"), (6, "medium"), (6, "hard"), (7, "medium"), (7, "hard"),
        (8, "hard"), (9, "expert")]
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}


def publish(puzzles: list[dict], out: Path) -> None:
    """Number the cases easy -> medium -> hard -> expert (smaller boards first) and write them.

    Builds into a scratch folder and swaps it in at the end, so docs/puzzles is never
    half-written (pushing mid-build would otherwise publish a broken site).
    """
    tmp = out.with_name(out.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    puzzles = sorted(puzzles, key=lambda p: (DIFFICULTY_ORDER[p["difficulty"]], p["size"]))
    index = []
    for i, puzzle in enumerate(puzzles):
        size = puzzle["size"]
        pid = f"case-{i + 1:03d}"
        puzzle["id"] = pid
        puzzle["title"] = f"Case #{i + 1}"
        (tmp / f"{pid}.json").write_text(json.dumps(puzzle, ensure_ascii=False), encoding="utf-8")
        blocked = sorted({r * size + c for o in puzzle["objects"] if not o["occupiable"] for r, c in o["cells"]})
        index.append({"id": pid, "title": puzzle["title"], "size": size, "difficulty": puzzle["difficulty"],
                      "rooms": [r["name"] for r in puzzle["rooms"]],
                      # enough to draw the little floor-plan preview on the case list
                      "grid": puzzle["grid"], "colors": [r["color"] for r in puzzle["rooms"]], "blocked": blocked})

    (tmp / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    print(f"Wrote {len(index)} puzzles to {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=27, help="number of puzzles")
    ap.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same puzzles)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "docs" / "puzzles")
    ap.add_argument("--reorder", action="store_true", help="only renumber the existing puzzles in --out")
    args = ap.parse_args()

    if args.reorder:
        index = json.loads((args.out / "index.json").read_text(encoding="utf-8"))
        puzzles = [json.loads((args.out / f"{e['id']}.json").read_text(encoding="utf-8")) for e in index]
        publish(puzzles, args.out)
        return

    puzzles = []
    for i in range(args.count):
        size, difficulty = PLAN[i % len(PLAN)]
        rng = random.Random(f"{args.seed}-{i}")
        t = time.perf_counter()
        puzzles.append(generate(size, difficulty, rng))
        print(f"{i + 1:>3}/{args.count}: {size}x{size} {difficulty:<6} "
              f"steps={puzzles[-1]['stats']}  {time.perf_counter() - t:.1f}s")
    publish(puzzles, args.out)


if __name__ == "__main__":
    main()
