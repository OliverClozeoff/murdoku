"""Clue types: how they read, whether they hold, and which ones are true for a solution."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .model import OBJECT_TYPES, Board, Cell

# Kinds that only constrain one person's cell.
UNARY = {"room", "not_room", "on", "beside_obj", "corner", "row_obj", "col_obj"}
# Kinds that relate two people's cells.
BINARY = {"same_room", "beside", "diagonal", "west", "east", "alone_with"}
# Kinds about how many people are in a room.
GLOBAL = {"empty", "count"}

# Clues that read like geometry rather than a story; used sparingly.
ABSTRACT = {"row_obj", "col_obj", "west", "east", "diagonal", "not_room"}

# Roughly how much a clue narrows things down. Hard puzzles strip strong clues first.
STRENGTH = {
    "room": 5, "on": 4, "alone_with": 4, "beside": 3, "beside_obj": 3, "alone": 3,
    "empty": 3, "corner": 2, "same_room": 2, "count": 2, "diagonal": 2,
    "row_obj": 1, "col_obj": 1, "not_room": 1, "west": 1, "east": 1,
}


@dataclass(frozen=True)
class Clue:
    kind: str
    p: int | None = None      # person the clue is about
    q: int | None = None      # second person (binary clues)
    obj: str | None = None    # object type key
    room: int | None = None   # room index
    k: int | None = None      # people count


def article(noun: str) -> str:
    return ("an " if noun[0].lower() in "aeiou" else "a ") + noun


def render(clue: Clue, names: list[str], board: Board) -> str:
    P = names[clue.p] if clue.p is not None else ""
    Q = names[clue.q] if clue.q is not None else ""
    room = board.room_names[clue.room] if clue.room is not None else ""
    obj = OBJECT_TYPES[clue.obj] if clue.obj else None
    match clue.kind:
        case "room": return f"{P} was in the {room}."
        case "not_room": return f"{P} was not in the {room}."
        case "on": return f"{P} was {obj.on_phrase}."
        case "beside_obj": return f"{P} was beside {article(obj.name)}."
        case "corner": return f"{P} was standing in a corner of a room."
        case "row_obj": return f"{P} was in the same row as {article(obj.name)}."
        case "col_obj": return f"{P} was in the same column as {article(obj.name)}."
        case "alone": return f"{P} was alone in a room."
        case "alone_with": return f"{P} was alone with {Q}."
        case "same_room": return f"{P} was in the same room as {Q}."
        case "beside": return f"{P} was beside {Q}."
        case "diagonal": return f"{P} was on the same diagonal as {Q}."
        case "west": return f"{P} was somewhere west of {Q}."
        case "east": return f"{P} was somewhere east of {Q}."
        case "empty": return f"Nobody was in the {room}."
        case "count":
            who = "person was" if clue.k == 1 else "people were"
            return f"Exactly {clue.k} {who} in the {room}."
    raise ValueError(clue.kind)


def unary_holds(clue: Clue, cell: Cell, board: Board) -> bool:
    match clue.kind:
        case "room": return board.room(cell) == clue.room
        case "not_room": return board.room(cell) != clue.room
        case "on": return board.obj_type(cell) == clue.obj
        case "beside_obj": return board.beside_object(cell, clue.obj)
        case "corner": return board.is_corner(cell)
        case "row_obj": return board.line_has_object(cell, clue.obj, "row")
        case "col_obj": return board.line_has_object(cell, clue.obj, "col")
    raise ValueError(clue.kind)


def binary_holds(clue: Clue, a: Cell, b: Cell, board: Board) -> bool:
    """a is the position of clue.p, b of clue.q. Room-exclusivity of alone_with is checked by the solver."""
    match clue.kind:
        case "same_room" | "alone_with": return board.room(a) == board.room(b)
        case "beside": return board.room(a) == board.room(b) and abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        case "diagonal": return abs(a[0] - b[0]) == abs(a[1] - b[1])
        case "west": return a[1] < b[1]
        case "east": return a[1] > b[1]
    raise ValueError(clue.kind)


def true_clues(board: Board, pos: list[Cell], victim: int, rng: random.Random) -> list[Clue]:
    """Every clue we are willing to print that holds for this solution."""
    n = len(pos)
    rooms = [board.room(c) for c in pos]
    counts = [rooms.count(r) for r in range(len(board.room_names))]
    out: list[Clue] = []

    for p, cell in enumerate(pos):
        out.append(Clue("room", p, room=rooms[p]))
        others = [r for r in range(len(board.room_names)) if r != rooms[p]]
        out.append(Clue("not_room", p, room=rng.choice(others)))
        t = board.obj_type(cell)
        if t and OBJECT_TYPES[t].occupiable:
            out.append(Clue("on", p, obj=t))
        for key in OBJECT_TYPES:
            if board.beside_object(cell, key):
                out.append(Clue("beside_obj", p, obj=key))
            if board.line_has_object(cell, key, "row") and rng.random() < 0.25:
                out.append(Clue("row_obj", p, obj=key))
            if board.line_has_object(cell, key, "col") and rng.random() < 0.25:
                out.append(Clue("col_obj", p, obj=key))
        if board.is_corner(cell):
            out.append(Clue("corner", p))
        if counts[rooms[p]] == 1:
            out.append(Clue("alone", p))

    for p in range(n):
        for q in range(p + 1, n):
            a, b = (p, q) if rng.random() < 0.5 else (q, p)
            same = rooms[p] == rooms[q]
            # "alone with the victim" would just announce the murderer, so skip it.
            if same and counts[rooms[p]] == 2 and victim not in (p, q):
                out.append(Clue("alone_with", a, b))
            elif same:
                out.append(Clue("same_room", a, b))
            if same and abs(pos[p][0] - pos[q][0]) + abs(pos[p][1] - pos[q][1]) == 1:
                out.append(Clue("beside", a, b))
            if abs(pos[p][0] - pos[q][0]) == abs(pos[p][1] - pos[q][1]):
                out.append(Clue("diagonal", a, b))
            if rng.random() < 0.25:
                kind = "west" if pos[a][1] < pos[b][1] else "east"
                out.append(Clue(kind, a, b))

    for r, cnt in enumerate(counts):
        if cnt == 0:
            out.append(Clue("empty", room=r))
        elif rng.random() < 0.5:
            out.append(Clue("count", room=r, k=cnt))
    return out
