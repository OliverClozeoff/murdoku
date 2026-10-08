"""Constraint model shared by the exhaustive solver and the step-by-step hint engine."""
from __future__ import annotations

from collections import defaultdict

from .clues import BINARY, UNARY, Clue, binary_holds, in_direction, unary_holds
from .model import Board, Cell


class Constraints:
    """All rules of a puzzle, compiled for fast checking.

    Built-in rules: one person per row and column, nobody on blocking objects,
    and the victim shares a room with exactly one other person (the murderer).
    """

    def __init__(self, board: Board, n_people: int, victim: int, clues: list[Clue]):
        self.board = board
        self.n = n_people
        self.consistent = True
        base = [c for c in board.cells if board.occupiable(c)]
        self.domains = [list(base) for _ in range(n_people)]
        self.links: dict[int, list[tuple[int, Clue, bool]]] = defaultdict(list)  # p -> (other, clue, p_is_first)
        self.person_cap: dict[int, int] = {victim: 2}  # exact head-count of this person's room
        self.room_cap: dict[int, int] = {}             # exact head-count of a room
        self.dir_counts: dict[int, list[tuple[str, int]]] = defaultdict(list)

        for cl in clues:
            if cl.kind in UNARY:
                self.domains[cl.p] = [c for c in self.domains[cl.p] if unary_holds(cl, c, board)]
            elif cl.kind in BINARY:
                self.links[cl.p].append((cl.q, cl, True))
                self.links[cl.q].append((cl.p, cl, False))
                if cl.kind == "alone_with":
                    self._cap_person(cl.p, 2)
                    self._cap_person(cl.q, 2)
            elif cl.kind == "alone":
                self._cap_person(cl.p, 1)
            elif cl.kind == "dir_count":
                self.dir_counts[cl.p].append((cl.obj, cl.k))
            elif cl.kind == "empty":
                self._cap_room(cl.room, 0)
            elif cl.kind == "count":
                self._cap_room(cl.room, cl.k)

        empty = {r for r, k in self.room_cap.items() if k == 0}
        self.domains = [[c for c in d if board.room(c) not in empty] for d in self.domains]

    def _cap_person(self, p: int, k: int) -> None:
        if self.person_cap.get(p, k) != k:
            self.consistent = False
        self.person_cap[p] = k

    def _cap_room(self, r: int, k: int) -> None:
        if self.room_cap.get(r, k) != k:
            self.consistent = False
        self.room_cap[r] = k

    # --- checks against a partial placement --------------------------------
    def fits(self, p: int, cell: Cell, pos: list[Cell | None]) -> bool:
        """Binary clues between p (at cell) and everyone already placed."""
        for other, cl, first in self.links[p]:
            o = pos[other]
            if o is not None:
                ok = binary_holds(cl, cell, o, self.board) if first else binary_holds(cl, o, cell, self.board)
                if not ok:
                    return False
        return True

    def counts_ok(self, pos: list[Cell | None], count: dict[int, int], final: bool) -> bool:
        """Head-count rules (alone, alone with, room counts, victim pair, direction counts)."""
        room = self.board.room
        for p, k in self.person_cap.items():
            if pos[p] is not None:
                c = count[room(pos[p])]
                if c > k or (final and c != k):
                    return False
        for r, k in self.room_cap.items():
            if count[r] > k or (final and count[r] != k):
                return False
        for p, rules in self.dir_counts.items():
            if pos[p] is None:
                continue
            for d, k in rules:
                inside = outside = 0
                for q, c in enumerate(pos):
                    if q != p and c is not None:
                        if in_direction(c, pos[p], d):
                            inside += 1
                        else:
                            outside += 1
                if inside > k or outside > self.n - 1 - k or (final and inside != k):
                    return False
        return True

    def candidates(self, p: int, pos: list[Cell | None], count: dict[int, int]) -> list[Cell]:
        """Squares p could still take given everyone already placed."""
        used_r = {c[0] for c in pos if c is not None}
        used_c = {c[1] for c in pos if c is not None}
        out = []
        for cell in self.domains[p]:
            if cell[0] in used_r or cell[1] in used_c or not self.fits(p, cell, pos):
                continue
            pos[p] = cell
            count[self.board.room(cell)] += 1
            if self.counts_ok(pos, count, False):
                out.append(cell)
            count[self.board.room(cell)] -= 1
            pos[p] = None
        return out


def solve(board: Board, n_people: int, victim: int, clues: list[Clue], limit: int = 2,
          start: list[Cell | None] | None = None, banned: set[tuple[int, Cell]] | None = None) -> list[list[Cell]]:
    """Return up to `limit` full solutions (person -> cell), optionally from a partial placement."""
    cons = Constraints(board, n_people, victim, clues)
    if not cons.consistent:
        return []
    banned = banned or set()
    pos: list[Cell | None] = list(start) if start else [None] * n_people
    count: dict[int, int] = defaultdict(int)
    for c in pos:
        if c is not None:
            count[board.room(c)] += 1
    solutions: list[list[Cell]] = []

    def rec() -> None:
        if len(solutions) >= limit:
            return
        free = [p for p in range(n_people) if pos[p] is None]
        if not free:
            if cons.counts_ok(pos, count, True):
                solutions.append(list(pos))  # type: ignore[arg-type]
            return
        best, best_cands = -1, None
        rows: set[int] = set()
        cols: set[int] = set()
        for p in free:
            cands = [c for c in cons.candidates(p, pos, count) if (p, c) not in banned]
            if not cands:
                return
            for r, c in cands:
                rows.add(r)
                cols.add(c)
            if best_cands is None or len(cands) < len(best_cands):
                best, best_cands = p, cands
        if len(rows) < len(free) or len(cols) < len(free):
            return
        for cell in best_cands:
            pos[best] = cell
            count[board.room(cell)] += 1
            rec()
            count[board.room(cell)] -= 1
            pos[best] = None
            if len(solutions) >= limit:
                return

    rec()
    return solutions
