"""Generate puzzles into docs/puzzles/ for the web game.

Usage:
    py generator/build.py --add 20             # keep every existing case, add 20 new ones (#34, #35, ...)
    py generator/build.py                      # build a brand-new set (replaces the existing cases!)
    py generator/build.py --count 30 --seed 7  # brand-new set, custom size/seed
    py generator/build.py --reorder            # re-label and renumber the existing set, no regenerating
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
from murdoku.generate import generate, measured_difficulty  # noqa: E402

# (size, difficulty) cycled through when building a set
# The difficulty here only steers clue choice; each case is labelled by how hard it measured.
PLAN = [(5, "easy"), (6, "easy"), (6, "medium"), (7, "medium"), (8, "medium"), (8, "hard"), (9, "hard"),
        (10, "hard"), (12, "expert"), (14, "expert"), (16, "expert")]
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}


def sort_key(p: dict) -> tuple:
    return DIFFICULTY_ORDER[p["difficulty"]], p["size"], p.get("id", "")


def publish(puzzles: list[dict], out: Path, renumber: bool = True) -> None:
    """Write the cases and the case list.

    renumber=True numbers everything easy -> expert (a brand-new set). renumber=False keeps
    every case's existing id and title; cases without one get the next free numbers.
    The case list is always sorted easy -> expert.

    Builds into a scratch folder and swaps it in at the end, so docs/puzzles is never
    half-written (pushing mid-build would otherwise publish a broken site).
    """
    tmp = out.with_name(out.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    if renumber:
        for p in puzzles:
            p.pop("id", None)
        puzzles = sorted(puzzles, key=sort_key)
    taken = [int(p["id"].split("-")[1]) for p in puzzles if p.get("id")]
    next_no = max(taken, default=0) + 1
    for puzzle in puzzles:
        if not puzzle.get("id"):
            puzzle["id"] = f"case-{next_no:03d}"
            puzzle["title"] = f"Case #{next_no}"
            next_no += 1

    index = []
    for puzzle in sorted(puzzles, key=sort_key):
        size = puzzle["size"]
        (tmp / f"{puzzle['id']}.json").write_text(json.dumps(puzzle, ensure_ascii=False), encoding="utf-8")
        blocked = sorted({r * size + c for o in puzzle["objects"] if not o["occupiable"] for r, c in o["cells"]})
        index.append({"id": puzzle["id"], "title": puzzle["title"], "size": size, "difficulty": puzzle["difficulty"],
                      "rooms": [r["name"] for r in puzzle["rooms"]],
                      # enough to draw the little floor-plan preview on the case list
                      "grid": puzzle["grid"], "colors": [r["color"] for r in puzzle["rooms"]], "blocked": blocked})

    (tmp / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    print(f"Wrote {len(index)} puzzles to {out}")


def load_existing(out: Path) -> list[dict]:
    if not (out / "index.json").exists():
        return []
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    return [json.loads((out / f"{e['id']}.json").read_text(encoding="utf-8")) for e in index]


def build(count: int, seed: int, stream: str, existing_grids: set) -> list[dict]:
    puzzles = []
    i = 0
    while len(puzzles) < count:
        size, difficulty = PLAN[(len(existing_grids) + i) % len(PLAN)]
        rng = random.Random(f"{seed}-{stream}{i}")
        i += 1
        t = time.perf_counter()
        puzzle = generate(size, difficulty, rng)
        fingerprint = json.dumps(puzzle["grid"])
        if fingerprint in existing_grids:
            continue  # same floor plan as a case we already have
        existing_grids.add(fingerprint)
        puzzles.append(puzzle)
        print(f"{len(puzzles):>3}/{count}: {size}x{size} {puzzle['difficulty']:<6} "
              f"steps={puzzle['stats']}  {time.perf_counter() - t:.1f}s", flush=True)
    return puzzles


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--add", type=int, metavar="N", help="keep the existing cases and add N new ones")
    ap.add_argument("--count", type=int, default=33, help="size of a brand-new set")
    ap.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same puzzles)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "docs" / "puzzles")
    ap.add_argument("--reorder", action="store_true", help="only re-label and renumber the existing puzzles")
    args = ap.parse_args()

    if args.reorder:
        puzzles = load_existing(args.out)
        for p in puzzles:  # re-label with the current difficulty rules
            p["difficulty"] = measured_difficulty(p["stats"], p["size"])
        publish(puzzles, args.out)
        return

    if args.add:
        existing = load_existing(args.out)
        grids = {json.dumps(p["grid"]) for p in existing}
        # a different random stream per existing set size, so repeated --add runs give new cases
        new = build(args.add, args.seed, f"add{len(existing)}-", grids)
        publish(existing + new, args.out, renumber=False)
        return

    publish(build(args.count, args.seed, "", set()), args.out)


if __name__ == "__main__":
    main()
