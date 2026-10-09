"""Human-style step solver. Produces the hint sequence and a difficulty measure.

Techniques, tried in order (simplest first):
  1. only square   - a person has exactly one square left
  2. only person   - a row/column can only be filled by one person
  3. look-ahead    - putting someone on a square would leave somebody else (or a row/column) with no options
  4. deep          - none of the above works; the step needs real trial and error
"""
from __future__ import annotations

from collections import defaultdict

from .clues import Clue, People, render
from .model import Board, Cell
from .solver import Constraints


LOOKAHEAD_MAX = 8  # only "what if" people with at most this many squares left


def rc(cell: Cell) -> str:
    return f"R{cell[0] + 1} C{cell[1] + 1}"


def explain(board: Board, victim: int, clues: list[Clue], solution: list[Cell],
            people: People, stop_when_stuck: bool = False) -> tuple[list[dict], dict]:
    """Solve step by step. With stop_when_stuck, return as soon as a guess would be needed:
    stats["stuck"] then holds {person: squares still possible} for everyone not yet placed."""
    n = len(solution)
    cons = Constraints(board, n, victim, clues, people.genders)
    names = people.names
    pos: list[Cell | None] = [None] * n
    count: dict[int, int] = defaultdict(int)
    elim: dict[int, set[Cell]] = defaultdict(set)
    notes: dict[int, list[str]] = defaultdict(list)   # reasoning gathered before a person's placement
    marked: dict[int, list[Cell]] = defaultdict(list)  # squares ruled out by that reasoning
    blocked: dict[int, dict[str, list[Cell]]] = defaultdict(dict)  # p -> reason -> squares it rules out
    steps: list[dict] = []
    stats = {"lookahead": 0, "deep": 0, "line": 0}  # lookahead = rounds that needed it

    own_clues = defaultdict(list)
    for cl in clues:
        if cl.p is not None:
            own_clues[cl.p].append(render(cl, people, board, own_card=False))

    def cands(p: int) -> list[Cell]:
        return [c for c in cons.candidates(p, pos, count) if c not in elim[p]]

    def place(p: int, cell: Cell, text: str, extra: list[Cell]) -> None:
        assert cell == solution[p], "hint engine drifted from the solution"
        parts = notes.pop(p, [])
        for reason, cells in list(blocked.pop(p, {}).items())[:2]:
            shown = [rc(c) for c in cells[:4]] + (["…"] if len(cells) > 4 else [])
            where = shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " or " + shown[-1]
            parts.append(f"{names[p]} can't be at {where}: {reason}.")
        lead = " ".join(parts)
        steps.append({
            "person": p,
            "cell": list(cell),
            "text": (lead + " " if lead else "") + text,
            "marks": [list(c) for c in dict.fromkeys(marked.pop(p, []) + extra) if c != cell],
        })
        pos[p] = cell
        count[board.room(cell)] += 1

    def clue_quote(p: int) -> str:
        if own_clues[p]:
            return " ".join(own_clues[p])
        if p == victim:
            return f"{names[p]} was alone with the murderer."
        return f"{names[p]} has no statement."

    while any(c is None for c in pos):
        free = [p for p in range(n) if pos[p] is None]
        C = {p: cands(p) for p in free}

        # 1. only square
        single = next((p for p in free if len(C[p]) == 1), None)
        if single is not None:
            cell = C[single][0]
            place(single, cell,
                  f"Look at {names[single]}: {clue_quote(single)} With the rows and columns already taken, "
                  f"the only square left is {rc(cell)}.", [])
            continue

        # 2. only person for a row / column
        progress = False
        for axis, label in ((0, "Row"), (1, "Column")):
            used = {c[axis] for c in pos if c is not None}
            for line in range(n):
                if line in used:
                    continue
                holders = [(p, [c for c in C[p] if c[axis] == line]) for p in free]
                holders = [h for h in holders if h[1]]
                if len(holders) != 1:
                    continue
                p, cells = holders[0]
                if len(cells) == 1:
                    stats["line"] += 1
                    place(p, cells[0],
                          f"{label} {line + 1} still needs someone, and {names[p]} is the only person who can "
                          f"stand there. {names[p]} goes to {rc(cells[0])}.", [])
                    progress = True
                    break
                outside = [c for c in C[p] if c[axis] != line]
                if outside:
                    elim[p].update(outside)
                    marked[p].extend(outside)
                    notes[p].append(f"Only {names[p]} can fill {label.lower()} {line + 1}, "
                                    f"so {names[p]} must be in that {label.lower()}.")
                    progress = True
                    break
            if progress:
                break
        if progress:
            continue

        # 3. look-ahead: a square is impossible if it leaves someone (or some line) with nothing.
        # Like a person would, only try this for people with a handful of squares left.
        for p in sorted(free, key=lambda q: len(C[q])):
            if len(C[p]) > LOOKAHEAD_MAX:
                break
            for cell in C[p]:
                pos[p] = cell
                count[board.room(cell)] += 1
                reason = None
                if not cons.counts_ok(pos, count, False):
                    reason = "one of the statements could no longer come true"
                rest = [q for q in free if q != p] if reason is None else []
                rows: set[int] = set()
                cols: set[int] = set()
                for q in rest:
                    cq = cands(q)
                    if not cq:
                        reason = f"{names[q]} would have nowhere left to go"
                        break
                    rows.update(c[0] for c in cq)
                    cols.update(c[1] for c in cq)
                if reason is None:
                    free_rows = set(range(n)) - {c[0] for c in pos if c is not None}
                    free_cols = set(range(n)) - {c[1] for c in pos if c is not None}
                    if free_rows - rows:
                        reason = f"nobody could fill row {min(free_rows - rows) + 1}"
                    elif free_cols - cols:
                        reason = f"nobody could fill column {min(free_cols - cols) + 1}"
                count[board.room(cell)] -= 1
                pos[p] = None
                if reason:
                    elim[p].add(cell)
                    marked[p].append(cell)
                    blocked[p].setdefault(reason, []).append(cell)
                    progress = True
            if progress:
                break
        if progress:
            stats["lookahead"] += 1
            continue

        # 4. deep reasoning: name the person with the fewest options and give the answer
        if stop_when_stuck:
            stats["stuck"] = {q: C[q] for q in free}
            return steps, stats
        p = min(free, key=lambda q: len(C[q]))
        stats["deep"] += 1
        others = [c for c in C[p] if c != solution[p]]
        place(p, solution[p],
              f"This one is tricky. {names[p]} could be at {', '.join(rc(c) for c in C[p])}. Follow each option "
              f"through: every square except {rc(solution[p])} eventually breaks a clue.", others)

    return steps, stats
