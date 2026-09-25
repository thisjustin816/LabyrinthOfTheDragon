"""BFS pathfinding over the game's own walkable-map files plus its Exit/Door
tables, so a suite can compute real step sequences instead of teleporting.

Exit tiles are not ordinary floor: arriving on one (map.c's handle_exit(),
matched purely by (map,x,y), any heading) immediately warps the player, so
they can never be walked "through" to reach something further away in the
same room. The graph models that: moving into a registered exit coordinate
is an edge straight to its destination, not a node with its own neighbors.

That destination isn't simply the Exit struct's to_col/to_row either:
MAP_STATE_EXIT_LOADED auto-walks the hero one more tile in the exit's own
`heading` right after arrival (map.c), unless heading is HERE (every hole
and portal) or the exit type is a hole. Floor 1's (12,3) exit, for one,
records to_col/to_row=(10,13) with heading UP, and stepping onto it settles
at (10,12). exit_by_src bakes that offset in at construction time so every
consumer gets the true rest tile.

Closed doors (tracked by the caller) block like walls; once opened they
behave like whatever they gate (usually also an exit). A tile drawn as a
stairway can't be stepped onto from the side (map.c's start_move()).
"""
import collections, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exits_db import EXITS, DOORS

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir))

FLOORS = {
    1: {"A": ("floor1_v2.tilemap", 32, 32)},
    2: {"A": ("floor2_v2.tilemap", 24, 24), "B": ("floor2_v2_b.tilemap", 32, 16)},
    3: {"A": ("floor3.tilemap", 32, 32)},
    4: {"A": ("floor4.tilemap", 32, 32)},
    5: {"A": ("floor5.tilemap", 32, 32), "B": ("floor5b.tilemap", 23, 7)},
    6: {"A": ("floor6.tilemap", 32, 32), "B": ("floor6b.tilemap", 16, 8)},
    7: {"A": ("floor7.tilemap", 32, 32)},
    8: {"A": ("floor8.tilemap", 32, 32)},
}

DIRS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
# Exit headings only: includes HERE, which is never a direction a path walks.
HEADING_DELTA = dict(DIRS, HERE=(0, 0))
# The tilemap graphics of src/map.h's DOOR_STAIRS_UP and DOOR_STAIRS_DOWN,
# through core.c's map_tile_lookup.
STAIRS_ART = {0x18, 0x24}
_grid_cache = {}


def load_grid(floor, map_letter="A"):
    """(collision rows, width, height, {(x, y) drawn as a stairway})."""
    key = (floor, map_letter)
    if key not in _grid_cache:
        fn, w, h = FLOORS[floor][map_letter]
        data = open(os.path.join(REPO, "res/maps", fn), "rb").read()
        _grid_cache[key] = ([[(data[2 * (x + y * w)] >> 6) for x in range(w)] for y in range(h)], w, h,
                            {(x, y) for y in range(h) for x in range(w)
                             if data[2 * (x + y * w)] & 0x3F in STAIRS_ART})
    return _grid_cache[key]


class Floor:
    """A floor's navigable graph: which maps it has, its exits and doors,
    and the caller's live door-open / extra-wall overrides."""

    def __init__(self, floor_num, open_doors=(), extra_walls=()):
        self.n = floor_num
        self.maps = FLOORS[floor_num]
        self.open_doors = set(open_doors)          # {(map,x,y)}
        self.extra_walls = set(extra_walls)         # e.g. floor6's live portals
        self.exit_by_src = {}
        for e in EXITS.get(floor_num, []):
            m, x, y, tm, tx, ty, heading = e
            dx, dy = HEADING_DELTA[heading]
            self.exit_by_src[(m, x, y)] = (tm, tx + dx, ty + dy, heading)
        self.door_by_pos = {}
        for m, x, y, key, start_open in DOORS.get(floor_num, []):
            self.door_by_pos[(m, x, y)] = (key, start_open)
            if start_open:
                self.open_doors.add((m, x, y))

    def is_door_closed(self, m, x, y):
        d = self.door_by_pos.get((m, x, y))
        return d is not None and (m, x, y) not in self.open_doors

    def _walkable(self, m, x, y):
        if (m, x, y) in self.extra_walls:
            return False
        grid, w, h, _ = load_grid(self.n, m)
        if not (0 <= x < w and 0 <= y < h):
            return False
        if self.is_door_closed(m, x, y):
            return False
        return grid[y][x] != 0

    def neighbor(self, m, x, y, direction):
        """(map,x,y) or None you actually end up at moving `direction` from
        here, following exit warps (already resolved to their post-arrival
        rest tile); None if that direction is blocked."""
        dx, dy = DIRS[direction]
        nx, ny = x + dx, y + dy
        if not self._walkable(m, nx, ny):
            return None
        if dx and (nx, ny) in load_grid(self.n, m)[3]:
            return None
        exit_ = self.exit_by_src.get((m, nx, ny))
        if exit_ and not self.is_door_closed(m, nx, ny):
            tm, tx, ty, heading = exit_
            return (tm if tm is not None else "NEXT_FLOOR", tx, ty)
        return (m, nx, ny)

    def path(self, src_map, src, dst_map, dst, face_adjacent=False):
        """Directions from (src_map,*src) to (dst_map,*dst).

        `face_adjacent`: dst is a non-walkable object tile (chest/sconce/
        sign/lever/npc) the player must stand next to and face, not stand on;
        returns (directions, final_facing) instead of directions."""
        if face_adjacent:
            best = None
            for facing, (dx, dy) in DIRS.items():
                nx, ny = dst[0] - dx, dst[1] - dy
                if self._walkable(dst_map, nx, ny) and (dst_map, nx, ny) not in self.exit_by_src:
                    p = self.path(src_map, src, dst_map, (nx, ny))
                    if p is not None and (best is None or len(p) < len(best[0])):
                        best = (p, facing)
            return best

        start = (src_map,) + tuple(src)
        goal = (dst_map,) + tuple(dst)
        if start == goal:
            return []
        q = collections.deque([start])
        prev = {start: None}
        while q:
            cur = q.popleft()
            if cur == goal:
                path = []
                node = cur
                while prev[node] is not None:
                    node, d = prev[node]
                    path.append(d)
                path.reverse()
                return path
            m, x, y = cur
            for d in DIRS:
                nxt = self.neighbor(m, x, y, d)
                if nxt is None or nxt in prev or nxt[0] == "NEXT_FLOOR":
                    continue
                prev[nxt] = (cur, d)
                q.append(nxt)
        return None

    def path_to_exit(self, src_map, src, exit_key):
        """Directions to reach and then step onto a registered exit tile
        `exit_key` = (map,x,y), triggering its warp as the final step.
        Returns the full direction list, or None if unreachable."""
        m, ex, ey = exit_key
        for facing, (dx, dy) in DIRS.items():
            if dx and (ex, ey) in load_grid(self.n, m)[3]:
                continue
            nx, ny = ex - dx, ey - dy
            if self._walkable(m, nx, ny) and (m, nx, ny) not in self.exit_by_src:
                p = self.path(src_map, src, m, (nx, ny))
                if p is not None:
                    return p + [facing]
        return None
