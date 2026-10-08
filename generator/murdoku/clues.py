"""Clue types: how they read, whether they hold, and which ones are true for a solution.

Rendered text marks keywords with *asterisks*; the web game shows them in bold.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .model import OBJECT_TYPES, Board, Cell

# Kinds that only constrain one person's cell.
UNARY = {"room", "not_room", "on", "not_on", "on_in", "beside_obj", "corner",
         "row_obj", "col_obj", "row_is", "col_is"}
# Kinds that relate two people's cells (p first, q second).
BINARY = {"with", "not_with", "alone_with", "beside", "diagonal",
          "west", "east", "north", "south", "one_north", "one_south", "one_west", "one_east"}
# "alone" caps the head-count of p's room; "dir_count" counts people in a direction from p.
# "empty" and "count" are about a room and don't belong to anyone.
GLOBAL = {"empty", "count"}

# Clues that read like geometry rather than a story; trimmed first so they're used sparingly.
ABSTRACT = {"row_obj", "col_obj", "west", "east", "north", "south", "diagonal", "not_room", "not_on"}

# Roughly how much a clue narrows things down. Hard puzzles strip strong clues first.
STRENGTH = {
    "on_in": 6, "room": 5, "on": 4, "alone_with": 4, "beside": 3, "beside_obj": 3, "alone": 3,
    "empty": 3, "row_is": 3, "col_is": 3, "one_north": 3, "one_south": 3, "one_west": 3, "one_east": 3,
    "corner": 2, "with": 2, "count": 2, "diagonal": 2, "dir_count": 2,
    "row_obj": 1, "col_obj": 1, "not_room": 1, "not_on": 1, "not_with": 1,
    "west": 1, "east": 1, "north": 1, "south": 1,
}

DIRECTIONS = ("north", "south", "west", "east")
NUMBERS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


@dataclass(frozen=True)
class Clue:
    kind: str
    p: int | None = None      # person the clue is about
    q: int | None = None      # second person (binary clues)
    obj: str | None = None    # object type key, or direction for dir_count
    room: int | None = None   # room index
    k: int | None = None      # a count, or a row/column index


def article(noun: str) -> str:
    return ("an " if noun[0].lower() in "aeiou" else "a ") + f"*{noun}*"


def in_direction(a: Cell, b: Cell, d: str) -> bool:
    """Is a strictly <d> of b?"""
    return {"north": a[0] < b[0], "south": a[0] > b[0], "west": a[1] < b[1], "east": a[1] > b[1]}[d]


@dataclass
class People:
    names: list[str]
    genders: list[str]

    def subj(self, i: int) -> str:
        return "She" if self.genders[i] == "f" else "He"

    def obj(self, i: int) -> str:
        return "her" if self.genders[i] == "f" else "him"


def render(clue: Clue, people: People, board: Board, own_card: bool = True) -> str:
    """Clue text. On a person's own card the subject becomes She/He, like the original."""
    S = people.subj(clue.p) if (own_card and clue.p is not None) else (people.names[clue.p] if clue.p is not None else "")
    Q = people.names[clue.q] if clue.q is not None else ""
    room = f"*{board.room_names[clue.room]}*" if clue.room is not None else ""
    otype = OBJECT_TYPES.get(clue.obj or "")
    n = board.size
    match clue.kind:
        case "room": return f"{S} was in the {room}."
        case "not_room": return f"{S} was *not* in the {room}."
        case "on": return f"{S} was {otype.on_phrase.format(a=article(otype.name))}."
        case "not_on": return f"{S} was *not* {otype.on_phrase.format(a=article(otype.name))}."
        case "on_in": return f"{S} was {otype.on_phrase.format(a=article(otype.name))} in the {room}."
        case "beside_obj": return f"{S} was *beside* {article(otype.name)}."
        case "corner": return f"{S} was in a *corner*."
        case "row_obj": return f"{S} was in the same *row* as {article(otype.name)}."
        case "col_obj": return f"{S} was in the same *column* as {article(otype.name)}."
        case "row_is": return f"{S} was in the *{'top' if clue.k == 0 else 'bottom'} row*."
        case "col_is": return f"{S} was in the *{'westernmost' if clue.k == 0 else 'easternmost'} column*."
        case "alone": return f"{S} was *alone*."
        case "alone_with": return f"{S} was *alone with* {Q}."
        case "with": return f"{S} was *with* {Q}."
        case "not_with": return f"{S} was *not with* {Q}."
        case "beside": return f"{S} was *beside* {Q}."
        case "diagonal": return f"{S} was on the same *diagonal* as {Q}."
        case "west" | "east" | "north" | "south": return f"{S} was somewhere *{clue.kind} of* {Q}."
        case "one_north" | "one_south":
            return f"{S} was exactly *one row {clue.kind[4:]} of* {Q}."
        case "one_west" | "one_east":
            return f"{S} was exactly *one column {clue.kind[4:]} of* {Q}."
        case "dir_count":
            if clue.k == 0:
                return f"Nobody was *{clue.obj} of* {people.obj(clue.p)}."
            who = "person was" if clue.k == 1 else "people were"
            return f"Exactly {NUMBERS[clue.k]} {who} *{clue.obj} of* {people.obj(clue.p)}."
        case "empty": return f"Nobody was in the {room}."
        case "count":
            who = "person was" if clue.k == 1 else "people were"
            return f"Exactly {NUMBERS[clue.k]} {who} in the {room}."
    raise ValueError(clue.kind)


def refs(clue: Clue, board: Board) -> dict:
    """What a clue mentions, so the game can highlight it on hover."""
    out: dict = {}
    if clue.room is not None:
        out["rooms"] = [clue.room]
    if clue.obj in OBJECT_TYPES:
        out["objects"] = [clue.obj]
    if clue.q is not None:
        out["people"] = [clue.q]
    if clue.kind == "row_is":
        out["rows"] = [clue.k]
    if clue.kind == "col_is":
        out["cols"] = [clue.k]
    return out


def unary_holds(clue: Clue, cell: Cell, board: Board) -> bool:
    match clue.kind:
        case "room": return board.room(cell) == clue.room
        case "not_room": return board.room(cell) != clue.room
        case "on": return board.obj_type(cell) == clue.obj
        case "not_on": return board.obj_type(cell) != clue.obj
        case "on_in": return board.obj_type(cell) == clue.obj and board.room(cell) == clue.room
        # Lenient on purpose: see Board.beside_object. true_clues() uses the strict reading.
        case "beside_obj": return board.beside_object(cell, clue.obj, lenient=True)
        case "corner": return board.is_corner(cell)
        case "row_obj": return board.line_has_object(cell, clue.obj, "row", lenient=True)
        case "col_obj": return board.line_has_object(cell, clue.obj, "col", lenient=True)
        case "row_is": return cell[0] == clue.k
        case "col_is": return cell[1] == clue.k
    raise ValueError(clue.kind)


def binary_holds(clue: Clue, a: Cell, b: Cell, board: Board) -> bool:
    """a is the position of clue.p, b of clue.q. Room exclusivity of alone_with is checked by the solver."""
    match clue.kind:
        case "with" | "alone_with": return board.room(a) == board.room(b)
        case "not_with": return board.room(a) != board.room(b)
        case "beside": return board.room(a) == board.room(b) and abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        case "diagonal": return abs(a[0] - b[0]) == abs(a[1] - b[1])
        case "west" | "east" | "north" | "south": return in_direction(a, b, clue.kind)
        case "one_north": return a[0] == b[0] - 1
        case "one_south": return a[0] == b[0] + 1
        case "one_west": return a[1] == b[1] - 1
        case "one_east": return a[1] == b[1] + 1
    raise ValueError(clue.kind)


def true_clues(board: Board, pos: list[Cell], victim: int, rng: random.Random) -> list[Clue]:
    """Every clue we are willing to print that holds for this solution."""
    n = len(pos)
    rooms = [board.room(c) for c in pos]
    counts = [rooms.count(r) for r in range(len(board.room_names))]
    present = {o.type for o in board.objects}
    out: list[Clue] = []

    for p, cell in enumerate(pos):
        out.append(Clue("room", p, room=rooms[p]))
        others = [r for r in range(len(board.room_names)) if r != rooms[p]]
        out.append(Clue("not_room", p, room=rng.choice(others)))
        t = board.obj_type(cell)
        if t and OBJECT_TYPES[t].occupiable:
            out.append(Clue("on", p, obj=t))
            out.append(Clue("on_in", p, obj=t, room=rooms[p]))
        seats = [k for k in present if OBJECT_TYPES[k].occupiable and k != t]
        if seats and rng.random() < 0.4:
            out.append(Clue("not_on", p, obj=rng.choice(seats)))
        for key in present:
            if board.beside_object(cell, key):
                out.append(Clue("beside_obj", p, obj=key))
            if board.line_has_object(cell, key, "row") and rng.random() < 0.2:
                out.append(Clue("row_obj", p, obj=key))
            if board.line_has_object(cell, key, "col") and rng.random() < 0.2:
                out.append(Clue("col_obj", p, obj=key))
        if board.is_corner(cell):
            out.append(Clue("corner", p))
        if cell[0] in (0, n - 1):
            out.append(Clue("row_is", p, k=cell[0]))
        if cell[1] in (0, n - 1):
            out.append(Clue("col_is", p, k=cell[1]))
        if counts[rooms[p]] == 1:
            out.append(Clue("alone", p))
        if rng.random() < 0.35:
            d = rng.choice(DIRECTIONS)
            k = sum(1 for q in range(n) if q != p and in_direction(pos[q], cell, d))
            out.append(Clue("dir_count", p, obj=d, k=k))

    for p in range(n):
        for q in range(p + 1, n):
            a, b = (p, q) if rng.random() < 0.5 else (q, p)
            pa, pb = pos[a], pos[b]
            same = rooms[p] == rooms[q]
            # "alone with the victim" would just announce the murderer, so skip it.
            if same and counts[rooms[p]] == 2 and victim not in (p, q):
                out.append(Clue("alone_with", a, b))
            elif same:
                out.append(Clue("with", a, b))
            elif rng.random() < 0.3:
                out.append(Clue("not_with", a, b))
            if same and abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) == 1:
                out.append(Clue("beside", a, b))
            if abs(pa[0] - pb[0]) == abs(pa[1] - pb[1]):
                out.append(Clue("diagonal", a, b))
            for kind, holds in (("one_north", pa[0] == pb[0] - 1), ("one_south", pa[0] == pb[0] + 1),
                                ("one_west", pa[1] == pb[1] - 1), ("one_east", pa[1] == pb[1] + 1)):
                if holds:
                    out.append(Clue(kind, a, b))
            if rng.random() < 0.2:
                d = rng.choice([d for d in DIRECTIONS if in_direction(pa, pb, d)])
                out.append(Clue(d, a, b))

    for r, cnt in enumerate(counts):
        if cnt == 0:
            out.append(Clue("empty", room=r))
        elif rng.random() < 0.4:
            out.append(Clue("count", room=r, k=cnt))
    return out
