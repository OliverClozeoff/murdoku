"""Puzzle generator: floor plan -> hidden solution -> clues -> trim clues while the answer stays unique."""
from __future__ import annotations

import base64
from collections import Counter
import json
import random

from .clues import (ABSTRACT, STRENGTH, UNARY, Clue, People, holds_full, refs, render, true_clues,
                    unary_holds)
from .hints import explain
from .model import OBJECT_TYPES, ROOM_TYPES, SUSPECTS, VICTIMS, Board, Cell, PlacedObject
from .solver import SearchLimit, solve
from .story import make_motive

SEARCH_BUDGET = 60_000  # nodes per uniqueness search before giving up on it
ROOM_COUNT = {4: (2, 3), 5: (3, 4), 6: (4, 5), 7: (4, 6), 8: (5, 7), 9: (5, 7), 10: (6, 8),
              11: (7, 9), 12: (7, 10), 13: (8, 11), 14: (9, 12), 15: (9, 13), 16: (10, 14)}
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
    """Pick a type per room. Some types appear twice (never side by side, bigger houses need
    more of these); each pair gets positional names like "North Bedroom" / "South Bedroom"."""
    n_rooms = max(max(row) for row in grid) + 1
    size = len(grid)
    adjacent = set()
    for r in range(size):
        for c in range(size):
            for rr, cc in ((r + 1, c), (r, c + 1)):
                if rr < size and cc < size and grid[rr][cc] != grid[r][c]:
                    adjacent.add(frozenset((grid[r][c], grid[rr][cc])))

    base = list(ROOM_TYPES)
    repeatable = [t for t, v in ROOM_TYPES.items() if v[3]]
    n_twins = max(0, n_rooms - len(base)) + (1 if n_rooms >= 4 and rng.random() < 0.7 else 0)
    if n_rooms >= 9 and rng.random() < 0.5:
        n_twins += 1  # big houses: a second pair is fun
    n_twins = min(n_twins, len(repeatable), n_rooms // 2)
    if n_rooms - n_twins > len(base):
        return None
    twins = rng.sample(repeatable, n_twins)
    singles = rng.sample([t for t in base if t not in twins], n_rooms - 2 * n_twins)
    types = singles + twins * 2
    for _ in range(300):
        rng.shuffle(types)
        if all(frozenset(i for i, x in enumerate(types) if x == t) not in adjacent for t in twins):
            break
    else:
        return None

    names = list(types)
    for t in twins:
        idxs = [i for i, x in enumerate(types) if x == t]
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


def make_appeal(pool: list[Clue], difficulty: str, victim: int, rng: random.Random):
    """Scoring for which clue to add next. Easy puzzles prefer strong clues ("in the Kitchen"),
    hard ones weak clues ("beside a plant")."""
    jitter = {c: rng.random() * 2.5 for c in pool}
    sign = {"easy": 1, "medium": 0, "hard": -1, "expert": -1}[difficulty]

    def appeal(c: Clue, load) -> float:
        # Abstract clues (rows, diagonals, compass) are a last resort; the victim's card mostly
        # just says "the victim"; spread statements evenly: people who already have some
        # count against, people with none get priority. `load` = statements per person so far.
        score = sign * STRENGTH[c.kind] + jitter[c] * (3 if sign == 0 else 1)
        score -= 10 if c.kind in ABSTRACT else 0
        score -= 5 if c.p == victim else 0
        if c.p is not None:
            score += 3 if load.get(c.p, 0) == 0 else -2 * load[c.p]
        return score
    return appeal


def select_clues(board: Board, n: int, victim: int, solution: list[Cell], pool: list[Clue],
                 appeal, genders: list[str]) -> list[Clue] | None:
    """Pick a small set of true clues with exactly one answer.

    Works upward: ask the solver for an answer other than the real one, add a clue that rules
    it out, repeat. Each round is one search that usually finishes fast, so this scales to big
    boards far better than starting from every clue and removing them one at a time.
    A cleanup pass then drops clues that turned out to be redundant.
    """
    chosen: list[Clue] = []
    for _ in range(4 * n + 20):
        try:
            sols = solve(board, n, victim, chosen, limit=2, genders=genders, max_nodes=SEARCH_BUDGET)
        except SearchLimit:
            return None  # too big to prove by search; the caller uses the engine instead
        other = next((s for s in sols if s != solution), None)
        if other is None:
            break
        ruling_out = [c for c in pool if c not in chosen and not holds_full(c, other, board, genders, victim)]
        if not ruling_out:
            return None  # can't happen when the full pool is unique, but stay safe
        load = Counter(c.p for c in chosen)
        chosen.append(max(ruling_out, key=lambda c: appeal(c, load)))
    else:
        return None

    # every suspect gets at least one statement on their card
    for q in range(n):
        if q != victim and not any(c.p == q for c in chosen):
            own = [c for c in pool if c.p == q]
            if own:
                chosen.append(max(own, key=lambda c: appeal(c, {})))

    # cleanup: drop clues the others already imply (least appealing first)
    for clue in sorted(chosen, key=lambda c: appeal(c, {})):
        if clue.p is not None and clue.p != victim and sum(1 for c in chosen if c.p == clue.p) <= 1:
            continue
        trial = [c for c in chosen if c != clue]
        try:
            if len(solve(board, n, victim, trial, limit=2, genders=genders, max_nodes=SEARCH_BUDGET)) == 1:
                chosen = trial
        except SearchLimit:
            pass  # can't tell quickly: keep the clue
    return chosen


def seed_clues(n: int, victim: int, pool: list[Clue], appeal) -> list[Clue]:
    """A starting point for the engine route: one appealing statement per suspect."""
    chosen: list[Clue] = []
    for q in range(n):
        own = [c for c in pool if c.p == q]
        if q != victim and own:
            chosen.append(max(own, key=lambda c: appeal(c, {})))
    return chosen


def make_logical(board: Board, victim: int, solution: list[Cell], clues: list[Clue], pool: list[Clue],
                 people: People, appeal) -> tuple[list[Clue], list[dict], dict] | None:
    """Make sure the step-by-step engine can solve the case without guessing.

    Wherever the engine gets stuck, add the most appealing clue that rules out at least one
    square still open to someone, then try again. Usually 0-3 rounds.
    """
    clues = list(clues)
    for _ in range(8 * len(solution)):
        steps, stats = explain(board, victim, clues, solution, people, stop_when_stuck=True)
        stuck = stats.pop("stuck", None)
        if stuck is None:
            return clues, steps, stats
        chosen_people = Counter(c.p for c in clues)

        def helps(c: Clue) -> bool:
            if c in clues:
                return False
            if c.kind in UNARY or c.kind in ("alone_type", "other_room"):
                return c.p in stuck and any(not unary_holds(c, cell, board) for cell in stuck[c.p])
            # relational clues: useful when they involve someone still open
            return c.p in stuck or c.q in stuck or c.p is None
        useful = [c for c in pool if helps(c)]
        if not useful:
            return None
        # big boards: add a couple at once so the engine is rerun fewer times
        useful.sort(key=lambda c: appeal(c, chosen_people), reverse=True)
        clues += useful[: 1 + len(stuck) // 6]
    return None


def make_easy(board: Board, victim: int, solution: list[Cell], clues: list[Clue], pool: list[Clue],
              people: People) -> list[Clue] | None:
    """Easy cases need no "what if" steps: keep adding the strongest unused clue (preferring
    people with the fewest statements) until the engine solves it by direct deduction alone."""
    clues = list(clues)
    for _ in range(3 * len(solution)):
        _, stats = explain(board, victim, clues, solution, people, stop_when_stuck=True)
        if "stuck" not in stats and stats["lookahead"] == 0:
            return clues
        spare = [c for c in pool if c not in clues and c.p is not None and c.p != victim]
        if not spare:
            return None
        load = {q: sum(1 for c in clues if c.p == q) for q in range(len(solution))}
        clues.append(max(spare, key=lambda c: (STRENGTH[c.kind] - 2 * load[c.p], c.kind not in ABSTRACT)))
    return None


def trim_logical(board: Board, victim: int, solution: list[Cell], clues: list[Clue], people: People,
                 appeal, difficulty: str) -> list[Clue]:
    """Drop clues (least appealing first) while the engine still solves the case without
    guessing and it doesn't get harder than asked for. Every suspect keeps a statement."""
    size = len(solution)
    ceiling = {"easy": 0, "medium": max(3, size // 2)}.get(difficulty)
    load = Counter(c.p for c in clues)
    for clue in sorted(clues, key=lambda c: (-load[c.p], appeal(c, {}))):
        if clue.p is not None and clue.p != victim and sum(1 for c in clues if c.p == clue.p) <= 1:
            continue
        trial = [c for c in clues if c != clue]
        _, stats = explain(board, victim, trial, solution, people, stop_when_stuck=True)
        if "stuck" in stats:
            continue
        if ceiling is not None and stats["lookahead"] > ceiling:
            continue
        clues = trial
    return clues


def measured_difficulty(stats: dict, size: int) -> str:
    """Name the difficulty after how much "what if" reasoning the engine needed."""
    la = stats["lookahead"]
    if la == 0:
        return "easy"
    if la <= max(3, size // 2):
        return "medium"
    if size >= 9 and la >= max(9, 0.6 * size):
        return "expert"  # expert is reserved for big boards
    return "hard"


def generate(size: int, difficulty: str, rng: random.Random, max_tries: int = 50) -> dict:
    """Build one case. `difficulty` steers which clues are preferred; the label on the case is
    measured afterwards from how the step-by-step engine solved it."""
    result = None
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

        # The cast comes first: clues like "a woman was in the other Bedroom" need genders.
        cast = rng.sample(SUSPECTS, size - 1)
        cast = cast[:victim] + [rng.choice(VICTIMS)] + cast[victim:]
        people = People([nm for nm, _ in cast], [g for _, g in cast])

        pool = true_clues(board, solution, victim, people.genders, rng)
        appeal = make_appeal(pool, difficulty, victim, rng)
        # Small boards: build a unique set by search, then let the engine check it.
        # Big boards (or when search runs over budget): let the engine pick the clues;
        # anything it solves without guessing has exactly one answer.
        clues = None
        if size <= 10:
            clues = select_clues(board, size, victim, solution, pool, appeal, people.genders)
        if clues is None:
            clues = seed_clues(size, victim, pool, appeal)
        fixed = make_logical(board, victim, solution, clues, pool, people, appeal)
        if fixed is None:
            continue
        clues = fixed[0]
        if difficulty == "easy":
            clues = make_easy(board, victim, solution, clues, pool, people)
            if clues is None:
                continue
        clues = trim_logical(board, victim, solution, clues, people, appeal, difficulty)
        hints, stats = explain(board, victim, clues, solution, people)
        result = (board, solution, victim, murderer, clues, people, hints, stats)
        break
    assert result is not None, "no case could be built"
    board, solution, victim, murderer, clues, people, hints, stats = result
    difficulty = measured_difficulty(stats, size)
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
