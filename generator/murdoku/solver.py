"""Backtracking solver: counts how many placements satisfy all the rules and clues."""
from __future__ import annotations

from collections import defaultdict

from .clues import BINARY, UNARY, Clue, binary_holds, unary_holds
from .model import Board, Cell


def solve(board: Board, n_people: int, victim: int, clues: list[Clue], limit: int = 2) -> list[list[Cell]]:
    """Return up to `limit` solutions (person -> cell).

    Built-in rules: one person per row and column, nobody on blocking objects,
    and the victim shares a room with exactly one other person (the murderer).
    """
    base = [c for c in board.cells if board.occupiable(c)]
    domains = [list(base) for _ in range(n_people)]
    links: dict[int, list[tuple[int, Clue, bool]]] = defaultdict(list)  # p -> (other, clue, p_is_first)
    person_cap: dict[int, int] = {victim: 2}  # exact head-count of this person's room
    room_cap: dict[int, int] = {}             # exact head-count of a room

    def cap_person(p: int, k: int) -> bool:
        if person_cap.get(p, k) != k:
            return False
        person_cap[p] = k
        return True

    for cl in clues:
        if cl.kind in UNARY:
            domains[cl.p] = [c for c in domains[cl.p] if unary_holds(cl, c, board)]
        elif cl.kind in BINARY:
            links[cl.p].append((cl.q, cl, True))
            links[cl.q].append((cl.p, cl, False))
            if cl.kind == "alone_with" and not (cap_person(cl.p, 2) and cap_person(cl.q, 2)):
                return []
        elif cl.kind == "alone":
            if not cap_person(cl.p, 1):
                return []
        elif cl.kind == "empty":
            room_cap[cl.room] = 0
        elif cl.kind == "count":
            if room_cap.get(cl.room, cl.k) != cl.k:
                return []
            room_cap[cl.room] = cl.k

    empty_rooms = {r for r, k in room_cap.items() if k == 0}
    domains = [[c for c in d if board.room(c) not in empty_rooms] for d in domains]

    pos: list[Cell | None] = [None] * n_people
    used_rows: set[int] = set()
    used_cols: set[int] = set()
    count = defaultdict(int)
    solutions: list[list[Cell]] = []

    def fits(p: int, cell: Cell) -> bool:
        for other, cl, first in links[p]:
            o = pos[other]
            if o is not None:
                ok = binary_holds(cl, cell, o, board) if first else binary_holds(cl, o, cell, board)
                if not ok:
                    return False
        return True

    def caps_ok(final: bool) -> bool:
        for p, k in person_cap.items():
            if pos[p] is not None:
                c = count[board.room(pos[p])]
                if c > k or (final and c != k):
                    return False
        for r, k in room_cap.items():
            if count[r] > k or (final and count[r] != k):
                return False
        return True

    def rec(placed: int) -> None:
        if len(solutions) >= limit:
            return
        if placed == n_people:
            if caps_ok(True):
                solutions.append(list(pos))  # type: ignore[arg-type]
            return
        best, best_cands = -1, None
        rows_reachable: set[int] = set()
        cols_reachable: set[int] = set()
        for p in range(n_people):
            if pos[p] is not None:
                continue
            cands = [c for c in domains[p] if c[0] not in used_rows and c[1] not in used_cols and fits(p, c)]
            if not cands:
                return
            for r, c in cands:
                rows_reachable.add(r)
                cols_reachable.add(c)
            if best_cands is None or len(cands) < len(best_cands):
                best, best_cands = p, cands
        free = n_people - placed
        if len(rows_reachable) < free or len(cols_reachable) < free:
            return
        for cell in best_cands:
            pos[best] = cell
            used_rows.add(cell[0]); used_cols.add(cell[1])
            count[board.room(cell)] += 1
            if caps_ok(False):
                rec(placed + 1)
            count[board.room(cell)] -= 1
            used_rows.discard(cell[0]); used_cols.discard(cell[1])
            pos[best] = None
            if len(solutions) >= limit:
                return

    rec(0)
    return solutions
