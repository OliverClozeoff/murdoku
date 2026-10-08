"""Core data: object/room catalogs and the board geometry used by clues and solver."""
from __future__ import annotations

from dataclasses import dataclass, field

Cell = tuple[int, int]


@dataclass(frozen=True)
class ObjectType:
    key: str
    name: str             # noun used in clues ("bed")
    icon: str             # shown on the board ("" = drawn with CSS only)
    occupiable: bool      # can a person stand/sit/lie here?
    on_phrase: str        # "lying on a bed" (only for occupiable objects)
    sizes: tuple[int, ...]


OBJECT_TYPES: dict[str, ObjectType] = {t.key: t for t in [
    # occupiable
    ObjectType("bed", "bed", "🛏️", True, "lying on a bed", (2,)),
    ObjectType("sofa", "sofa", "🛋️", True, "sitting on a sofa", (2,)),
    ObjectType("chair", "chair", "🪑", True, "sitting on a chair", (1,)),
    ObjectType("carpet", "carpet", "", True, "standing on a carpet", (1, 2)),
    ObjectType("bathtub", "bathtub", "🛁", True, "in a bathtub", (2,)),
    ObjectType("bench", "bench", "🪵", True, "sitting on a bench", (2,)),
    ObjectType("car", "car", "🚗", True, "in a car", (2,)),
    # blocking
    ObjectType("table", "table", "🍽️", False, "", (1, 2)),
    ObjectType("shelf", "shelf", "📚", False, "", (1,)),
    ObjectType("plant", "plant", "🪴", False, "", (1,)),
    ObjectType("tv", "TV", "📺", False, "", (1,)),
    ObjectType("tree", "tree", "🌳", False, "", (1,)),
    ObjectType("sink", "sink", "🚰", False, "", (1,)),
    ObjectType("toolbox", "toolbox", "🧰", False, "", (1,)),
]}

# Room name -> (floor color, object types that may appear there)
ROOM_TYPES: dict[str, tuple[str, list[str]]] = {
    "Kitchen": ("#f7e2a0", ["table", "chair", "sink", "plant"]),
    "Living Room": ("#c3d9f3", ["sofa", "tv", "carpet", "plant", "chair"]),
    "Bedroom": ("#f4c8da", ["bed", "carpet", "shelf", "plant"]),
    "Study": ("#d8cdf3", ["shelf", "chair", "table", "carpet"]),
    "Dining Room": ("#f7cbb0", ["table", "chair", "plant"]),
    "Library": ("#dcc5a5", ["shelf", "chair", "carpet", "sofa"]),
    "Bathroom": ("#b7e4e6", ["bathtub", "sink", "carpet"]),
    "Garden": ("#c4e5b1", ["tree", "bench", "plant"]),
    "Hallway": ("#e4e1da", ["carpet", "plant", "shelf"]),
    "Garage": ("#c3c8d2", ["car", "toolbox", "shelf"]),
}

SUSPECT_NAMES = [
    "Alice", "Bruno", "Clara", "Dmitri", "Edith", "Felix", "Greta", "Hugo",
    "Ines", "Jasper", "Kira", "Leon", "Mona", "Nico", "Olga", "Pablo",
    "Quinn", "Rosa", "Silas", "Tessa", "Umar", "Wendy", "Xavier", "Yara", "Zane",
]
VICTIM_NAMES = ["Victor", "Vera", "Vincent", "Violet", "Vivian"]


@dataclass
class PlacedObject:
    type: str
    cells: list[Cell]


@dataclass
class Board:
    """Floor plan: rooms and objects on a size x size grid."""
    size: int
    room_of: list[list[int]]          # room index per cell
    room_names: list[str]
    objects: list[PlacedObject] = field(default_factory=list)
    obj_of: list[list[int]] = field(default_factory=list)  # object index per cell, -1 = none

    def __post_init__(self) -> None:
        if not self.obj_of:
            self.obj_of = [[-1] * self.size for _ in range(self.size)]

    # --- geometry helpers -------------------------------------------------
    @property
    def cells(self) -> list[Cell]:
        return [(r, c) for r in range(self.size) for c in range(self.size)]

    def room(self, cell: Cell) -> int:
        return self.room_of[cell[0]][cell[1]]

    def obj(self, cell: Cell) -> int:
        return self.obj_of[cell[0]][cell[1]]

    def obj_type(self, cell: Cell) -> str | None:
        i = self.obj(cell)
        return self.objects[i].type if i >= 0 else None

    def occupiable(self, cell: Cell) -> bool:
        t = self.obj_type(cell)
        return t is None or OBJECT_TYPES[t].occupiable

    def neighbors(self, cell: Cell) -> list[Cell]:
        r, c = cell
        out = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                out.append((nr, nc))
        return out

    def same_room_neighbors(self, cell: Cell) -> list[Cell]:
        return [n for n in self.neighbors(cell) if self.room(n) == self.room(cell)]

    def is_corner(self, cell: Cell) -> bool:
        """A corner is where a horizontal and a vertical wall of the room meet."""
        r, c = cell
        room = self.room(cell)

        def wall(nr: int, nc: int) -> bool:
            return not (0 <= nr < self.size and 0 <= nc < self.size) or self.room_of[nr][nc] != room

        horizontal = wall(r - 1, c) or wall(r + 1, c)
        vertical = wall(r, c - 1) or wall(r, c + 1)
        return horizontal and vertical

    def beside_object(self, cell: Cell, obj_type: str) -> bool:
        """Orthogonally next to a *different* object of this type, in the same room."""
        own = self.obj(cell)
        for n in self.same_room_neighbors(cell):
            o = self.obj(n)
            if o >= 0 and o != own and self.objects[o].type == obj_type:
                return True
        return False

    def line_has_object(self, cell: Cell, obj_type: str, axis: str) -> bool:
        """Same row (axis='row') or column as another object of this type."""
        own = self.obj(cell)
        r, c = cell
        line = [(r, k) for k in range(self.size)] if axis == "row" else [(k, c) for k in range(self.size)]
        for other in line:
            o = self.obj(other)
            if o >= 0 and o != own and self.objects[o].type == obj_type:
                return True
        return False
