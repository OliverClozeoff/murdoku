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
    """Grow rooms from random seeds; growth favors cells that hug the room, giving compact shapes."""
    k = rng.randint(*ROOM_COUNT[size])
    grid = [[-1] * size for _ in range(size)]
    seeds = rng.sample([(r, c) for r in range(size) for c in range(size)], k)
    for i, (r, c) in enumerate(seeds):
        grid[r][c] = i
    remaining = size * size - k
    while remaining:
        room = rng.randrange(k)
        frontier: list[tuple[int, Cell]] = []
        for r in range(size):
            for c in range(size):
                if grid[r][c] != -1:
                    continue
                touching = sum(
                    1 for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                    if 0 <= nr < size and 0 <= nc < size and grid[nr][nc] == room
                )
                if touching:
                    frontier.append((touching, (r, c)))
        if not frontier:
            continue
        weights = [t ** 3 for t, _ in frontier]
        _, (r, c) = rng.choices(frontier, weights)[0]
        grid[r][c] = room
        remaining -= 1
    sizes = [sum(row.count(i) for row in grid) for i in range(k)]
    return grid if min(sizes) >= MIN_ROOM_CELLS else None


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
    for room_idx, name in enumerate(board.room_names):
        allowed = ROOM_TYPES[name][2]
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
               rng: random.Random) -> list[Clue]:
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
        if len(solve(board, n, victim, trial, limit=2)) == 1:
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
        n_rooms = max(max(row) for row in grid) + 1
        board = Board(size, grid, rng.sample(list(ROOM_TYPES), n_rooms))
        picked = pick_solution(board, rng)
        if picked is None:
            continue
        solution, victim, murderer = picked
        place_objects(board, solution, rng)

        clues = true_clues(board, solution, victim, rng)
        if solve(board, size, victim, clues, limit=2) != [solution]:
            continue  # rare: even every true clue can't pin it down
        clues = trim_clues(board, size, victim, clues, difficulty, rng)

        cast = rng.sample(SUSPECTS, size - 1)
        cast = cast[:victim] + [rng.choice(VICTIMS)] + cast[victim:]
        people = People([nm for nm, _ in cast], [g for _, g in cast])
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
        "rooms": [{"name": nm, "color": ROOM_TYPES[nm][0], "floor": ROOM_TYPES[nm][1]} for nm in board.room_names],
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
