"""Tile maps: a grid of square tiles taken from a tile sheet. Tile (0, 0) is centred on the object's position."""
import re

MAX_TILES = 200000


def key(c, r):
    return f"{int(c)},{int(r)}"


def split(k):
    c, r = k.split(",")
    return int(c), int(r)


def get(o, c, r):
    """Tile number at a cell, or -1 when the cell is empty."""
    return o.tiles.get(key(c, r), -1)


def set_tile(o, c, r, n):
    k = key(c, r)
    if n is None or n < 0:
        if k in o.tiles:
            del o.tiles[k]
            o.tile_ver += 1
    elif o.tiles.get(k) != n:
        if len(o.tiles) >= MAX_TILES and k not in o.tiles:
            return False
        o.tiles[k] = int(n)
        o.tile_ver += 1
    return True


def clear(o):
    o.tiles = {}
    o.tile_ver += 1


def cell_at(o, wx, wy):
    """Which cell contains this world position?"""
    ox, oy = o.world_pos()
    ts = max(1, o.tile_size)
    return int((wx - ox + ts / 2) // ts), int((wy - oy + ts / 2) // ts)


def from_text(o, text, legend):
    """Fill from lines of text. `legend` maps a character to a tile number; other characters leave the cell empty."""
    clear(o)
    for r, line in enumerate(str(text).strip("\n").split("\n")):
        for c, ch in enumerate(line):
            n = legend.get(ch)
            if isinstance(n, (int, float)) and not isinstance(n, bool):
                set_tile(o, c, r, int(n))


def solid_rects(o):
    """(cx, cy, w, h) boxes for collision: tiles in a row are merged into one box. Cached until the tiles change."""
    ts = o.tile_size
    stamp = (o.tile_ver, len(o.tiles), ts)
    if o._rect_cache is not None and o._rect_cache[0] == stamp:
        return o._rect_cache[1]
    rows = {}
    for k in o.tiles:
        c, r = split(k)
        rows.setdefault(r, []).append(c)
    out = []
    for r, cols in rows.items():
        cols.sort()
        start = prev = cols[0]
        for c in cols[1:] + [None]:
            if c is not None and c == prev + 1:
                prev = c
                continue
            out.append(((start + prev) / 2.0 * ts, r * ts, (prev - start + 1) * ts, ts))
            if c is not None:
                start = prev = c
    o._rect_cache = (stamp, out)
    return out


def bounds(o):
    """(min_col, min_row, max_col, max_row) of the painted tiles, or None."""
    if not o.tiles:
        return None
    cs, rs = zip(*(split(k) for k in o.tiles))
    return min(cs), min(rs), max(cs), max(rs)
