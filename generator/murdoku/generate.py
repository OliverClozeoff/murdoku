"""Puzzle generator: floor plan -> hidden solution -> clues -> trim clues while the answer stays unique."""
from __future__ import annotations

import base64
import json
import random

from .clues import ABSTRACT, STRENGTH, Clue, People, refs, render, true_clues
from .hints import explain
from .model import OBJECT_TYPES, ROOM_TYPES, SUSPECTS, VICTIMS, Board, Cell, PlacedObject
from .solver import solve
from .story import make_motive

ROOM_COUNT = {4: (2, 3), 5: (3, 4), 6: (4, 5), 7: (4, 6), 8: (5, 7), 9: (5, 7), 10: (6, 8)}
MIN_ROOM_CELLS = 3


def make_rooms(size: int, rng: random.Random) -> list[list[int]] | None:
    """Cut the grid into rectangles (binary space partition), then merge a pair or two
    into L-shapes. Gives floor plans that read like buildings instead of blobs."""
    k = rng.randint(*ROOM_COUNT[size])
    merges = rng.choice([0, 1, 1, 2]) if size >= 6 else rng.choice([0, 1])
    rects = [(0, 0, size, size)]  # (row, col, height, width)

    def cuts(rect):
        r, c, h, w = rect
        out = []
        for t in range(1, h):  # horizontal cut after t rows
            if t * w >= MIN_ROOM_CELLS and (h - t) * w >= MIN_ROOM_CELLS:
                out.append(("h", t))
        for t in range(1, w):
            if t * h >= MIN_ROOM_CELLS and (w - t) * h >= MIN_ROOM_CELLS:
                out.append(("v", t))
        return out

    while len(rects) < k + merges:
        options = [x for x in rects if cuts(x)]
        if not options:
            return None
        rect = rng.choices(options, [(x[2] * x[3]) ** 2 for x in options])[0]
        r, c, h, w = rect
        possible = cuts(rect)
        # cut across the long side, near the middle, so rooms don't become slivers
        long_axis = "h" if h > w else "v" if w > h else rng.choice("hv")
        preferred = [x for x in possible if x[0] == long_axis] or possible
        span = h if preferred[0][0] == "h" else w
        axis, t = rng.choices(preferred, [1 + span - abs(span / 2 - x[1]) * 2 for x in preferred])[0]
        rects.remove(rect)
        if axis == "h":
            rects += [(r, c, t, w), (r + t, c, h - t, w)]
        else:
            rects += [(r, c, h, t), (r, c + t, h, w - t)]

    rooms = [{(rr, cc) for rr in range(r, r + h) for cc in range(c, c + w)} for r, c, h, w in rects]
    for _ in range(merges):
        pairs = []
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                touching = any((a + 1, b) in rooms[j] or (a, b + 1) in rooms[j] or (a - 1, b) in rooms[j]
                               or (a, b - 1) in rooms[j] for a, b in rooms[i])
                union = rooms[i] | rooms[j]
                rs = [x for x, _ in union]
                cs = [y for _, y in union]
                is_rect = (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1) == len(union)
                if touching and not is_rect and len(union) <= size * size * 0.4:
                    pairs.append((i, j))
        if not pairs:
            break
        i, j = rng.choice(pairs)
        rooms[i] |= rooms.pop(j)

    grid = [[-1] * size for _ in range(size)]
    for idx, cells in enumerate(rooms):
        for r, c in cells:
            grid[r][c] = idx
    if max(len(x) for x in rooms) > size * size * 0.45:
        return None
    return grid


def name_rooms(grid: list[list[int]], rng: random.Random) -> tuple[list[str], list[str]] | None:
    """Pick a type per room. Often one type appears twice (never side by side); the pair
    then gets positional names like "North Bedroom" / "South Bedroom"."""
    n_rooms = max(max(row) for row in grid) + 1
    size = len(grid)
    adjacent = set()
    for r in range(size):
        for c in range(size):
            for rr, cc in ((r + 1, c), (r, c + 1)):
                if rr < size and cc < size and grid[rr][cc] != grid[r][c]:
                    adjacent.add(frozenset((grid[r][c], grid[rr][cc])))
    types = rng.sample(list(ROOM_TYPES), n_rooms)
    if n_rooms >= 4 and rng.random() < 0.7:
        apart = [(a, b) for a in range(n_rooms) for b in range(a + 1, n_rooms)
                 if frozenset((a, b)) not in adjacent]
        if not apart:
            return None
        twin = rng.choice([t for t, v in ROOM_TYPES.items() if v[3]])
        a, b = rng.choice(apart)
        rest = [t for t in types if t != twin][: n_rooms - 2]
        types = []
        for i in range(n_rooms):
            types.append(twin if i in (a, b) else rest.pop())
    names = list(types)
    for t in set(types):
        idxs = [i for i, x in enumerate(types) if x == t]
        if len(idxs) != 2:
            continue
        centers = []
        for i in idxs:
            cells = [(r, c) for r in range(size) for c in range(size) if grid[r][c] == i]
            centers.append((sum(r for r, _ in cells) / len(cells), sum(c for _, c in cells) / len(cells)))
        (r1, c1), (r2, c2) = centers
        if abs(r1 - r2) >= abs(c1 - c2):
            first, second = ("North", "South") if r1 < r2 else ("South", "North")
        else:
            first, second = ("West", "East") if c1 < c2 else ("East", "West")
        names[idxs[0]], names[idxs[1]] = f"{first} {t}", f"{second} {t}"
    return names, types


def pick_solution(board: Board, rng: random.Random) -> tuple[list[Cell], int, int] | None:
    """Random one-per-row/column placement where some room holds exactly two people."""
    n = board.size
    for _ in range(200):
        cols = list(range(n))
        rng.shuffle(cols)
        cells = [(r, cols[r]) for r in range(n)]
        rooms = [board.room(c) for c in cells]
        pairs = [r for r in set(rooms) if rooms.count(r) == 2]
        if pairs:
            crime_room = rng.choice(pairs)
            a, b = [i for i, r in enumerate(rooms) if r == crime_room]
            victim, murderer = (a, b) if rng.random() < 0.5 else (b, a)
            return cells, victim, murderer
    return None


def place_objects(board: Board, solution: list[Cell], rng: random.Random) -> None:
    """Furnish each room. Blocking objects never cover a solution cell."""
    taken = set(solution)
    for room_idx, rtype in enumerate(board.room_types):
        allowed = ROOM_TYPES[rtype][2]
        room_cells = [c for c in board.cells if board.room(c) == room_idx]
        target = max(1, round(len(room_cells) * rng.uniform(0.25, 0.45)))
        for _ in range(target * 4):
            if target == 0:
                break
            otype = OBJECT_TYPES[rng.choice(allowed)]
            length = rng.choice(otype.sizes)
            start = rng.choice(room_cells)
            if length == 1:
                cells = [start]
            else:
                dr, dc = rng.choice([(0, 1), (1, 0)])
                cells = [start, (start[0] + dr, start[1] + dc)]
            if any(not (0 <= r < board.size and 0 <= c < board.size) for r, c in cells):
                continue
            if any(board.room(c) != room_idx or board.obj(c) != -1 for c in cells):
                continue
            if not otype.occupiable and any(c in taken for c in cells):
                continue
            board.objects.append(PlacedObject(otype.key, cells))
            for r, c in cells:
                board.obj_of[r][c] = len(board.objects) - 1
            target -= 1


def trim_clues(board: Board, n: int, victim: int, clues: list[Clue], difficulty: str,
               rng: random.Random, genders: list[str]) -> list[Clue]:
    """Drop clues one at a time as long as the solution stays unique.

    Easy puzzles try to drop weak clues first (so the strong ones survive);
    hard puzzles try to drop strong clues first.
    """
    jitter = {c: rng.random() * 2.5 for c in clues}
    sign = {"easy": 1, "medium": 0, "hard": -1, "expert": -1}[difficulty]

    def priority(c: Clue) -> float:
        # Abstract clues (rows, diagonals, compass) go first so puzzles lean on rooms and furniture.
        # The victim's own clues go early too: the victim's card mostly just says "the victim".
        abstract = -10 if c.kind in ABSTRACT else 0
        victims = -5 if c.p == victim else 0
        return abstract + victims + sign * STRENGTH[c.kind] + jitter[c] * (3 if sign == 0 else 1)

    kept = list(clues)
    for clue in sorted(clues, key=priority):
        # Every suspect keeps at least one clue about them.
        if clue.p is not None and clue.p != victim and sum(1 for c in kept if c.p == clue.p) <= 1:
            continue
        trial = [c for c in kept if c != clue]
        if len(solve(board, n, victim, trial, limit=2, genders=genders)) == 1:
            kept = trial
    return kept


def difficulty_fits(difficulty: str, stats: dict, size: int) -> bool:
    """Match the requested difficulty to how the step solver had to work.

    "lookahead" counts the rounds where a what-if check was needed; bigger boards
    naturally need more of them, so the bands grow with the board.
    """
    if stats["deep"]:
        return False  # never ship a puzzle that needs trial and error
    la = stats["lookahead"]
    if difficulty == "easy":
        return la == 0
    if difficulty == "medium":
        return 1 <= la <= max(3, size - 3)
    if difficulty == "hard":
        return la >= 3
    return la >= size  # expert


def generate(size: int, difficulty: str, rng: random.Random, max_tries: int = 300) -> dict:
    best = None
    for _ in range(max_tries):
        grid = make_rooms(size, rng)
        if grid is None:
            continue
        named = name_rooms(grid, rng)
        if named is None:
            continue
        board = Board(size, grid, named[0], room_types=named[1])
        picked = pick_solution(board, rng)
        if picked is None:
            continue
        solution, victim, murderer = picked
        place_objects(board, solution, rng)

        # The cast comes first now: clues like "a woman was in the other Bedroom" need genders.
        cast = rng.sample(SUSPECTS, size - 1)
        cast = cast[:victim] + [rng.choice(VICTIMS)] + cast[victim:]
        people = People([nm for nm, _ in cast], [g for _, g in cast])

        clues = true_clues(board, solution, victim, people.genders, rng)
        if solve(board, size, victim, clues, limit=2, genders=people.genders) != [solution]:
            continue  # rare: even every true clue can't pin it down
        clues = trim_clues(board, size, victim, clues, difficulty, rng, people.genders)

        hints, stats = explain(board, victim, clues, solution, people)
        if best is None or (best[-1]["deep"] and not stats["deep"]):
            best = (board, solution, victim, murderer, clues, people, hints, stats)
        if difficulty_fits(difficulty, stats, size):
            best = (board, solution, victim, murderer, clues, people, hints, stats)
            break
    assert best is not None
    board, solution, victim, murderer, clues, people, hints, stats = best
    names = people.names

    by_person: dict[int, list[Clue]] = {i: [] for i in range(size)}
    facts: list[Clue] = []
    for c in clues:
        (facts if c.p is None else by_person[c.p]).append(c)

    def entry(c: Clue) -> dict:
        return {"text": render(c, people, board), "refs": refs(c, board)}

    crime_room = board.room_names[board.room(solution[victim])]
    motive = make_motive(names[murderer], names[victim], crime_room, rng)
    secret = {"cells": [list(c) for c in solution], "murderer": murderer, "motive": motive, "hints": hints}
    return {
        "size": size,
        "difficulty": difficulty,
        "stats": stats,
        "rooms": [{"name": nm, "type": t, "color": ROOM_TYPES[t][0], "floor": ROOM_TYPES[t][1]}
                  for nm, t in zip(board.room_names, board.room_types)],
        "grid": board.room_of,
        "objects": [
            {
                "type": o.type,
                "name": OBJECT_TYPES[o.type].name,
                "icon": OBJECT_TYPES[o.type].icon,
                "occupiable": OBJECT_TYPES[o.type].occupiable,
                "cells": [list(c) for c in o.cells],
            }
            for o in board.objects
        ],
        "people": [
            {
                "name": nm,
                "letter": nm[0],
                "gender": people.genders[i],
                "victim": i == victim,
                "clues": [entry(c) for c in sorted(by_person[i], key=lambda c: -STRENGTH[c.kind])],
            }
            for i, nm in enumerate(names)
        ],
        "facts": [entry(c) for c in facts],
        # Base64 only keeps the answer from being spoiled at a glance; it isn't security.
        "secret": base64.b64encode(json.dumps(secret).encode()).decode(),
    }
