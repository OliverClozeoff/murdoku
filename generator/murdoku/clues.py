"""Clue types: how they read, whether they hold, and which ones are true for a solution.

Rendered text marks keywords with *asterisks*; the web game shows them in bold.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .model import OBJECT_TYPES, Board, Cell

# Kinds that only constrain one person's cell.
UNARY = {"room", "not_room", "on", "not_on", "on_in", "beside_obj", "corner",
         "row_obj", "col_obj", "row_is", "col_is", "edge2", "on_either", "in_type"}
# Kinds that relate two people's cells (p first, q second).
BINARY = {"with", "not_with", "alone_with", "beside", "diagonal",
          "west", "east", "north", "south", "one_north", "one_south", "one_west", "one_east"}
# Kinds that say *someone* (anyone but p, maybe of a given gender) is in a set of squares
# that depends on where p is. The solver checks them as soon as p is placed.
EXISTS = {"someone_obj_col", "someone_beside_row", "other_room", "gender_with"}
# "alone" / "alone_type" cap the head-count of p's room; "dir_count" counts people in a
# direction from p; "empty_beside" needs an empty neighbouring room.
# "empty" and "count" are about a room and don't belong to anyone.
GLOBAL = {"empty", "count"}

# Clues that read like geometry rather than a story; trimmed first so they're used sparingly.
ABSTRACT = {"row_obj", "col_obj", "west", "east", "north", "south", "diagonal", "not_room", "not_on"}

# Roughly how much a clue narrows things down. Hard puzzles strip strong clues first.
STRENGTH = {
    "on_in": 6, "room": 5, "on": 4, "alone_with": 4, "alone_type": 4,
    "beside": 3, "beside_obj": 3, "alone": 3, "empty": 3, "row_is": 3, "col_is": 3,
    "one_north": 3, "one_south": 3, "one_west": 3, "one_east": 3,
    "corner": 2, "with": 2, "count": 2, "diagonal": 2, "dir_count": 2, "edge2": 2, "on_either": 2,
    "in_type": 2, "other_room": 2, "someone_obj_col": 2, "someone_beside_row": 2, "empty_beside": 2,
    "gender_with": 1, "row_obj": 1, "col_obj": 1, "not_room": 1, "not_on": 1, "not_with": 1,
    "west": 1, "east": 1, "north": 1, "south": 1,
}

DIRECTIONS = ("north", "south", "west", "east")
NUMBERS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
           "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]
EDGE2 = ["in the *first or second column*", "in the *last or second-to-last column*",
         "in the *top two rows*", "in the *bottom two rows*"]
GENDER_WORD = {"f": "woman", "m": "man"}


@dataclass(frozen=True)
class Clue:
    kind: str
    p: int | None = None      # person the clue is about
    q: int | None = None      # second person (binary clues)
    obj: str | None = None    # object type key, or direction for dir_count
    room: int | None = None   # room index
    k: int | None = None      # a count, an index, or a signed row/column offset
    obj2: str | None = None   # second object type ("on a chair or in a car")
    rtype: str | None = None  # room type ("a Bedroom")
    g: str | None = None      # gender the "someone" must have ("f"/"m"), None = anyone


def article(noun: str) -> str:
    return ("an " if noun[0].lower() in "aeiou" else "a ") + f"*{noun}*"


def in_direction(a: Cell, b: Cell, d: str) -> bool:
    """Is a strictly <d> of b?"""
    return {"north": a[0] < b[0], "south": a[0] > b[0], "west": a[1] < b[1], "east": a[1] > b[1]}[d]


def on_text(key: str) -> str:
    t = OBJECT_TYPES[key]
    return t.on_phrase.format(a=article(t.name))


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
    O = (people.obj(clue.p) if own_card else people.names[clue.p]) if clue.p is not None else ""
    Q = people.names[clue.q] if clue.q is not None else ""
    room = f"*{board.room_names[clue.room]}*" if clue.room is not None else ""
    otype = OBJECT_TYPES.get(clue.obj or "")
    match clue.kind:
        case "room": return f"{S} was in the {room}."
        case "not_room": return f"{S} was *not* in the {room}."
        case "on": return f"{S} was {on_text(clue.obj)}."
        case "not_on": return f"{S} was *not* {on_text(clue.obj)}."
        case "on_in": return f"{S} was {on_text(clue.obj)} in the {room}."
        case "on_either": return f"{S} was {on_text(clue.obj)} *or* {on_text(clue.obj2)}."
        case "beside_obj": return f"{S} was *beside* {article(otype.name)}."
        case "corner": return f"{S} was in a *corner*."
        case "row_obj": return f"{S} was in the same *row* as {article(otype.name)}."
        case "col_obj": return f"{S} was in the same *column* as {article(otype.name)}."
        case "row_is": return f"{S} was in the *{'top' if clue.k == 0 else 'bottom'} row*."
        case "col_is": return f"{S} was in the *{'westernmost' if clue.k == 0 else 'easternmost'} column*."
        case "edge2": return f"{S} was {EDGE2[clue.k]}."
        case "in_type": return f"{S} was in {article(clue.rtype)}."
        case "alone": return f"{S} was *alone*."
        case "alone_type": return f"{S} was *alone* in {article(clue.rtype)}."
        case "alone_with": return f"{S} was *alone with* {Q}."
        case "with": return f"{S} was *with* {Q}."
        case "not_with": return f"{S} was *not with* {Q}."
        case "gender_with": return f"{S} was *with* a *{GENDER_WORD[clue.g]}*."
        case "other_room":
            return (f"{S} was in {article(clue.rtype)}. There was a *{GENDER_WORD[clue.g]}* "
                    f"in the *other* {clue.rtype}.")
        case "beside": return f"{S} was *beside* {Q}."
        case "diagonal": return f"{S} was on the same *diagonal* as {Q}."
        case "west" | "east" | "north" | "south": return f"{S} was somewhere *{clue.kind} of* {Q}."
        case "one_north" | "one_south":
            return f"{S} was exactly *one row {clue.kind[4:]} of* {Q}."
        case "one_west" | "one_east":
            return f"{S} was exactly *one column {clue.kind[4:]} of* {Q}."
        case "someone_obj_col":
            d = "west" if clue.k < 0 else "east"
            cols = "column" if abs(clue.k) == 1 else "columns"
            return f"Exactly *{NUMBERS[abs(clue.k)]} {cols} {d} of* {O}, someone was {on_text(clue.obj)}."
        case "someone_beside_row":
            d = "north" if clue.k < 0 else "south"
            rows = "row" if abs(clue.k) == 1 else "rows"
            return f"*{NUMBERS[abs(clue.k)].capitalize()} {rows} {d} of* {O}, someone was *beside* {article(otype.name)}."
        case "empty_beside":
            return f"{S} was *beside a wall*, with an *empty room* on the other side."
        case "dir_count":
            if clue.k == 0:
                return f"Nobody was *{clue.obj} of* {O}."
            who = "person was" if clue.k == 1 else "people were"
            return f"Exactly {NUMBERS[clue.k]} {who} *{clue.obj} of* {O}."
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
    if clue.rtype is not None:
        out["rooms"] = board.rooms_of_type(clue.rtype)
    objs = [o for o in (clue.obj, clue.obj2) if o in OBJECT_TYPES]
    if objs:
        out["objects"] = objs
    if clue.q is not None:
        out["people"] = [clue.q]
    if clue.kind == "row_is":
        out["rows"] = [clue.k]
    if clue.kind == "col_is":
        out["cols"] = [clue.k]
    if clue.kind == "edge2":
        n = board.size
        out["cols" if clue.k < 2 else "rows"] = [0, 1] if clue.k % 2 == 0 else [n - 2, n - 1]
    return out


def edge2_holds(k: int, cell: Cell, n: int) -> bool:
    v = cell[1] if k < 2 else cell[0]
    return v in ((0, 1) if k % 2 == 0 else (n - 2, n - 1))


def unary_holds(clue: Clue, cell: Cell, board: Board) -> bool:
    match clue.kind:
        case "room": return board.room(cell) == clue.room
        case "not_room": return board.room(cell) != clue.room
        case "on": return board.obj_type(cell) == clue.obj
        case "not_on": return board.obj_type(cell) != clue.obj
        case "on_in": return board.obj_type(cell) == clue.obj and board.room(cell) == clue.room
        case "on_either": return board.obj_type(cell) in (clue.obj, clue.obj2)
        # Lenient on purpose: see Board.beside_object. true_clues() uses the strict reading.
        case "beside_obj": return board.beside_object(cell, clue.obj, lenient=True)
        case "corner": return board.is_corner(cell)
        case "row_obj": return board.line_has_object(cell, clue.obj, "row", lenient=True)
        case "col_obj": return board.line_has_object(cell, clue.obj, "col", lenient=True)
        case "row_is": return cell[0] == clue.k
        case "col_is": return cell[1] == clue.k
        case "edge2": return edge2_holds(clue.k, cell, board.size)
        case "in_type" | "alone_type" | "other_room": return board.room_types[board.room(cell)] == clue.rtype
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


def target_cells(clue: Clue, a: Cell, board: Board, lenient: bool = True) -> list[Cell]:
    """For an EXISTS clue about p standing at a: the squares where 'someone' has to be."""
    n = board.size
    match clue.kind:
        case "someone_obj_col":
            col = a[1] + clue.k
            if not 0 <= col < n:
                return []
            return [(r, col) for r in range(n) if board.obj_type((r, col)) == clue.obj]
        case "someone_beside_row":
            row = a[0] + clue.k
            if not 0 <= row < n:
                return []
            return [(row, c) for c in range(n)
                    if board.occupiable((row, c)) and board.beside_object((row, c), clue.obj, lenient=lenient)]
        case "other_room":
            here = board.room(a)
            return [c for r in board.rooms_of_type(clue.rtype) if r != here for c in board.room_cells[r]]
        case "gender_with":
            return [c for c in board.room_cells[board.room(a)] if c != a]
    raise ValueError(clue.kind)


def empty_neighbour_rooms(a: Cell, board: Board) -> set[int]:
    """Rooms on the other side of a wall next to a."""
    return {board.room(nb) for nb in board.neighbors(a) if board.room(nb) != board.room(a)}


def true_clues(board: Board, pos: list[Cell], victim: int, genders: list[str],
               rng: random.Random) -> list[Clue]:
    """Every clue we are willing to print that holds for this solution."""
    n = len(pos)
    rooms = [board.room(c) for c in pos]
    counts = [rooms.count(r) for r in range(len(board.room_names))]
    present = {o.type for o in board.objects}
    seats_present = [k for k in present if OBJECT_TYPES[k].occupiable]
    type_count = {t: board.room_types.count(t) for t in board.room_types}
    out: list[Clue] = []

    for p, cell in enumerate(pos):
        rtype = board.room_types[rooms[p]]
        out.append(Clue("room", p, room=rooms[p]))
        others = [r for r in range(len(board.room_names)) if r != rooms[p]]
        out.append(Clue("not_room", p, room=rng.choice(others)))
        t = board.obj_type(cell)
        if t and OBJECT_TYPES[t].occupiable:
            out.append(Clue("on", p, obj=t))
            out.append(Clue("on_in", p, obj=t, room=rooms[p]))
            alts = [k for k in seats_present if k != t]
            if alts:
                a, b = (t, rng.choice(alts)) if rng.random() < 0.5 else (rng.choice(alts), t)
                out.append(Clue("on_either", p, obj=a, obj2=b))
        seats = [k for k in seats_present if k != t]
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
        for k in range(4):
            if edge2_holds(k, cell, n) and rng.random() < 0.5:
                out.append(Clue("edge2", p, k=k))
        if type_count[rtype] > 1:
            out.append(Clue("in_type", p, rtype=rtype))
            if counts[rooms[p]] == 1:
                out.append(Clue("alone_type", p, rtype=rtype))
            other = [r for r in board.rooms_of_type(rtype) if r != rooms[p]]
            for g in {genders[q] for q in range(n) if q != p and rooms[q] in other}:
                out.append(Clue("other_room", p, rtype=rtype, g=g))
        if counts[rooms[p]] == 1:
            out.append(Clue("alone", p))
        for g in {genders[q] for q in range(n) if q != p and rooms[q] == rooms[p]}:
            if rng.random() < 0.5:
                out.append(Clue("gender_with", p, g=g))
        if any(counts[r] == 0 for r in empty_neighbour_rooms(cell, board)):
            out.append(Clue("empty_beside", p))
        if rng.random() < 0.35:
            d = rng.choice(DIRECTIONS)
            k = sum(1 for q in range(n) if q != p and in_direction(pos[q], cell, d))
            out.append(Clue("dir_count", p, obj=d, k=k))
        # "Exactly two columns west of her, someone was in a car." / "Two rows north of him,
        # someone was beside a plant." Built from where the others actually are.
        for q in range(n):
            if q == p:
                continue
            dc, dr = pos[q][1] - cell[1], pos[q][0] - cell[0]
            tq = board.obj_type(pos[q])
            if tq and OBJECT_TYPES[tq].occupiable and 1 <= abs(dc) <= 3 and rng.random() < 0.5:
                out.append(Clue("someone_obj_col", p, obj=tq, k=dc))
            if 1 <= abs(dr) <= 3:
                for key in present:
                    if board.beside_object(pos[q], key) and rng.random() < 0.12:
                        out.append(Clue("someone_beside_row", p, obj=key, k=dr))

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
    return list(dict.fromkeys(out))  # drop duplicates, keep order


def holds_full(clue: Clue, pos: list[Cell], board: Board, genders: list[str], victim: int) -> bool:
    """Does a clue hold on a complete placement? (Same lenient reading as the solver.)"""
    n = len(pos)
    rooms = [board.room(c) for c in pos]
    p, k = clue.p, clue.kind
    a = pos[p] if p is not None else None
    others = [q for q in range(n) if q != p]
    if k in UNARY:
        return unary_holds(clue, a, board)
    if k in BINARY:
        if not binary_holds(clue, a, pos[clue.q], board):
            return False
        return k != "alone_with" or rooms.count(rooms[p]) == 2
    g_ok = lambda q: clue.g is None or genders[q] == clue.g
    match k:
        case "alone":
            return rooms.count(rooms[p]) == 1
        case "alone_type":
            return rooms.count(rooms[p]) == 1 and board.room_types[rooms[p]] == clue.rtype
        case "empty":
            return rooms.count(clue.room) == 0
        case "count":
            return rooms.count(clue.room) == clue.k
        case "dir_count":
            return sum(in_direction(pos[q], a, clue.obj) for q in others) == clue.k
        case "empty_beside":
            return any(rooms.count(r) == 0 for r in empty_neighbour_rooms(a, board))
        case "other_room":
            if board.room_types[rooms[p]] != clue.rtype:
                return False
        case _ if k not in EXISTS:
            raise ValueError(k)
    squares = set(target_cells(clue, a, board))
    return any(pos[q] in squares and g_ok(q) for q in others)
