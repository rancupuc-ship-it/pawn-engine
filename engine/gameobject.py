"""One object in a scene. Pure python (no Qt)."""
import copy
import uuid

SAVE_FIELDS = ["name", "kind", "x", "y", "w", "h", "angle", "color", "sprite", "text", "text_size",
               "align", "active", "body", "solid", "hud", "follow", "zoom", "layer", "flip_x", "alpha", "tags",
               "sheet_cols", "sheet_rows", "frame", "anims", "anim", "font", "friction", "bounce",
               "anchor", "value", "checked", "enabled", "radius", "back_color", "hover_color", "press_color",
               "text_color", "locked", "one_way", "trigger", "slope", "cgroup", "cmask",
               "points", "tiles", "tile_size", "em_rate", "em_life", "em_speed", "em_spread", "em_dir", "em_size",
               "em_gravity", "em_on", "parallax", "intensity", "flicker", "em_color_end", "em_alpha_end", "em_size_end",
               "em_size_var", "em_speed_var", "em_life_var", "em_spin", "em_spin_var", "em_drag", "em_wind", "em_shape",
               "em_radius", "em_add", "em_local", "em_inherit", "em_max"]
UI_KINDS = ("button", "bar", "slider", "checkbox", "input")
NO_LOOK_KINDS = ("model", "folder", "zone", "spawn", "beam")      # nothing is drawn for these while the game runs
KINDS = ("rect", "circle", "sprite", "text", "camera", "empty", "polygon", "tilemap", "particles", "light",
         "model", "folder", "zone", "spawn", "beam", "prompt") + UI_KINDS

# Where a screen-fixed (HUD) object is measured from: fractions of the half-screen from the camera centre.
ANCHORS = {"none": None, "center": (0, 0), "top-left": (-1, -1), "top": (0, -1), "top-right": (1, -1),
           "left": (-1, 0), "right": (1, 0), "bottom-left": (-1, 1), "bottom": (0, 1), "bottom-right": (1, 1)}
VIEW_HALF = (480.0, 270.0)      # the game screen is always 960 x 540 units


EM_RANGES = {"em_rate": (0, 5000, 30.0), "em_life": (0.05, 60, 1.0), "em_speed": (0, 5000, 120.0), "em_spread": (0, 360, 360.0),
             "em_dir": (-720, 720, -90.0), "em_size": (0.5, 500, 8.0), "em_gravity": (-5000, 5000, 0.0),
             "em_alpha_end": (0, 1, 0.0), "em_size_end": (0, 5, 0.4), "em_size_var": (0, 1, 0.0),
             "em_speed_var": (0, 1, 0.4), "em_life_var": (0, 1, 0.3), "em_spin": (-3600, 3600, 0.0),
             "em_spin_var": (0, 3600, 0.0), "em_drag": (0, 20, 0.0), "em_wind": (-5000, 5000, 0.0),
             "em_radius": (0, 2000, 0.0), "em_inherit": (0, 1, 0.0), "em_max": (1, 20000, 1500)}


def particles_clean(o):
    """Make every particle setting a sane number, whatever the file or a script put there."""
    for k, (lo, hi, default) in EM_RANGES.items():
        v = getattr(o, k)
        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")
        v = max(lo, min(hi, v)) if ok else default
        setattr(o, k, int(v) if k == "em_max" else float(v))
    if o.em_shape not in ("point", "circle", "box", "line"):
        o.em_shape = "point"
    if not isinstance(o.em_color_end, str):
        o.em_color_end = ""
    o.em_add, o.em_local, o.em_on = bool(o.em_add), bool(o.em_local), bool(o.em_on)


def _count(v):
    return max(1, min(256, int(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else 1


def _clean_points(pts):
    out = []
    if isinstance(pts, list):
        for p in pts[:512]:
            if isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p):
                out.append([float(p[0]), float(p[1])])
    return out


def _clean_tiles(t):
    out = {}
    if isinstance(t, dict):
        for k, v in t.items():
            try:
                c, r = str(k).split(",")
                int(c), int(r)
            except ValueError:
                continue
            if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                out[f"{int(c)},{int(r)}"] = v
    return out


def base_name(name):
    """'Coin (3)' -> 'Coin'. Names without a ' (number)' ending are returned unchanged."""
    if name.endswith(")"):
        i = name.rfind(" (")
        if i > 0 and name[i + 2:-1].isdigit():
            return name[:i]
    return name


class GameObject:
    def __init__(self, name="Object", kind="rect", **kw):
        self.id = uuid.uuid4().hex[:8]
        self.name = name
        self.kind = kind
        self.x = 0.0
        self.y = 0.0
        self.w = 100.0
        self.h = 100.0
        self.angle = 0.0
        self.color = "#4fd1b5"
        self.sprite = ""
        self.text = "Text"
        self.text_size = 32
        self.align = "center"
        self.active = True
        self.locked = False    # editor only: can't be picked in the scene view
        self.body = False      # affected by gravity
        self.solid = False     # things can stand on it
        self.hud = False       # stays on screen (offset from camera)
        self.follow = ""       # camera only
        self.zoom = 1.0        # camera only
        self.layer = 0         # draw order: higher layers are drawn on top
        self.flip_x = False    # mirror a sprite left-right
        self.alpha = 1.0       # 0 = invisible, 1 = solid
        self.tags = []         # labels such as "enemy"; find them with tagged("enemy")
        self.sheet_cols = 1    # sprite sheet: how many pictures across ...
        self.sheet_rows = 1    # ... and down
        self.frame = 0         # which picture of the sheet is shown
        self.anims = {}        # {"run": {"frames": [0, 1, 2], "fps": 10, "loop": True}}
        self.anim = ""         # animation that starts playing by itself
        self.font = ""         # font file inside the project, like assets/fonts/pixel.ttf
        self.friction = 0.0    # how fast sideways speed fades on the ground (0 = never)
        self.bounce = 0.0      # 0 = no bounce, 1 = bounces back as fast as it hit
        self.anchor = "none"   # HUD objects: which screen edge or corner they are measured from
        self.value = 0.0       # bar / slider: 0 to 1
        self.checked = False   # checkbox
        self.enabled = True    # UI: untick to ignore the mouse
        self.radius = -1       # UI corner roundness (-1 = use the theme)
        self.back_color = ""   # UI colors: empty means "use the theme"
        self.hover_color = ""
        self.press_color = ""
        self.text_color = ""
        self.one_way = False   # solid only from above: bodies can jump up through it
        self.trigger = False   # not solid; only reports overlaps (on touch / on untouch)
        self.slope = ""        # "", "up-right" or "up-left": a ramp (a right triangle filling the box)
        self.cgroup = 1        # collision group 1-8: which group this object is in
        self.cmask = 255       # collision mask: which groups (bits 1-8) this object collides with
        self.points = []       # polygon corners, [[x, y], ...] from -0.5 to 0.5 (scaled by width and height)
        self.tiles = {}        # tilemap: {"col,row": picture number in the tile sheet}
        self.tile_size = 32    # tilemap: size of one square tile
        self.em_rate = 30.0    # particles: how many appear per second
        self.em_life = 1.0     # seconds each one lives
        self.em_speed = 120.0  # start speed
        self.em_spread = 360.0 # angle they spread over (360 = every direction)
        self.em_dir = -90.0    # centre direction (-90 = up)
        self.em_size = 8.0     # start size
        self.em_gravity = 0.0  # pulls them down (negative lifts them up)
        self.em_on = True      # keeps emitting
        self.em_color_end = ""     # particles fade toward this color ("" = keep the start color)
        self.em_alpha_end = 0.0    # opacity at the end of life (1 = stays solid, 0 = fades out)
        self.em_size_end = 0.4     # size at the end of life, as a fraction of the start size
        self.em_size_var = 0.0     # random size difference, 0 to 1
        self.em_speed_var = 0.4    # random speed difference, 0 to 1
        self.em_life_var = 0.3     # random lifetime difference, 0 to 1
        self.em_spin = 0.0         # turning speed in degrees per second
        self.em_spin_var = 0.0     # random extra spin
        self.em_drag = 0.0         # slows them down (0 = never, 3 = quickly)
        self.em_wind = 0.0         # sideways push (negative = left)
        self.em_shape = "point"    # where they start: point, circle, box or line
        self.em_radius = 0.0       # size of the circle shape
        self.em_add = False        # glowing blend (colors add up)
        self.em_local = False      # move together with the emitter
        self.em_inherit = 0.0      # how much of the emitter's own speed they start with, 0 to 1
        self.em_max = 1500         # most particles alive at once
        self.parallax = 1.0    # 1 moves with the world, 0 stays on screen, 0.5 moves half as fast (far away)
        self.intensity = 1.0   # light: how strongly it cuts through the darkness (uses width as its size)
        self.flicker = 0.0     # light: how much the strength wobbles, 0 to 1
        self.scripts = []      # [{"file": "player.pawn", "values": {}}]
        self.children = []
        self.parent = None
        self.vy = 0.0          # runtime only
        self.vx = 0.0
        self.on_ground = False
        self.dead = False
        self.hovered = False   # UI: mouse is over it
        self.pressing = False  # UI: mouse button is down on it
        self.focused = False   # UI: text input has the keyboard
        self.anim_name = ""    # animation playing right now
        self.anim_t = 0.0
        self.anim_done = False
        self.parts = []        # particles alive right now: [x, y, vx, vy, age, life]
        self.em_acc = 0.0
        self.tile_ver = 0      # bumped when tiles change, so cached collision boxes get rebuilt
        self._rect_cache = None
        for k, v in kw.items():
            setattr(self, k, v)

    # ---- saving ------------------------------------------------------------
    def to_dict(self):
        d = {k: getattr(self, k) for k in SAVE_FIELDS}
        d["tags"] = list(self.tags)
        d["anims"] = copy.deepcopy(self.anims)
        d["points"] = copy.deepcopy(self.points)
        d["tiles"] = dict(self.tiles)
        d["id"] = self.id
        d["scripts"] = copy.deepcopy(self.scripts)
        d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d, parent=None):
        o = cls()
        for k in SAVE_FIELDS:
            if k in d:
                setattr(o, k, d[k])
        o.tags = list(o.tags) if isinstance(o.tags, list) else []
        o.anims = copy.deepcopy(o.anims) if isinstance(o.anims, dict) else {}
        o.parallax = float(o.parallax) if isinstance(o.parallax, (int, float)) and not isinstance(o.parallax, bool) else 1.0
        o.intensity = max(0.0, min(2.0, float(o.intensity))) if isinstance(o.intensity, (int, float)) else 1.0
        o.flicker = max(0.0, min(1.0, float(o.flicker))) if isinstance(o.flicker, (int, float)) else 0.0
        o.cgroup = o.cgroup if isinstance(o.cgroup, int) and 1 <= o.cgroup <= 8 else 1
        o.cmask = o.cmask if isinstance(o.cmask, int) and 0 <= o.cmask <= 255 else 255
        o.points = _clean_points(o.points)
        o.tiles = _clean_tiles(o.tiles)
        o.tile_size = max(4, min(512, int(o.tile_size))) if isinstance(o.tile_size, (int, float)) and not isinstance(o.tile_size, bool) else 32
        if o.slope not in ("", "up-right", "up-left"):
            o.slope = ""
        o.sheet_cols = _count(o.sheet_cols)
        o.sheet_rows = _count(o.sheet_rows)
        particles_clean(o)
        o.id = d.get("id", o.id)
        o.scripts = copy.deepcopy(d.get("scripts", []))
        o.parent = parent
        o.children = [cls.from_dict(c, o) for c in d.get("children", [])]
        return o

    def clone(self):
        o = GameObject.from_dict(self.to_dict())
        for n in o.iter_tree():
            n.id = uuid.uuid4().hex[:8]
        return o

    def collides_with(self, other):
        """Do the collision groups of the two objects allow them to collide? (Both must agree.)"""
        return bool((self.cmask >> (other.cgroup - 1)) & 1 and (other.cmask >> (self.cgroup - 1)) & 1)

    # ---- positions -----------------------------------------------------------
    def anchor_offset(self, cam):
        """Distance from the camera centre to this HUD object's anchor (cam may carry the zoom as a 3rd value)."""
        a = ANCHORS.get(self.anchor)
        if not a:
            return 0.0, 0.0
        zoom = cam[2] if len(cam) > 2 and cam[2] else 1.0
        return a[0] * VIEW_HALF[0] / zoom, a[1] * VIEW_HALF[1] / zoom

    def world_pos(self, cam=(0.0, 0.0)):
        if self.parent is None:
            if self.hud:
                ax, ay = self.anchor_offset(cam)
                return self.x + cam[0] + ax, self.y + cam[1] + ay
            if self.parallax != 1.0:
                k = 1.0 - self.parallax
                return self.x + cam[0] * k, self.y + cam[1] * k
            return self.x, self.y
        px, py = self.parent.world_pos(cam)
        return px + self.x, py + self.y

    def set_world_pos(self, wx, wy, cam=(0.0, 0.0)):
        if self.parent is None:
            if self.hud:
                ax, ay = self.anchor_offset(cam)
                self.x, self.y = wx - cam[0] - ax, wy - cam[1] - ay
            elif self.parallax != 1.0:
                k = 1.0 - self.parallax
                self.x, self.y = wx - cam[0] * k, wy - cam[1] * k
            else:
                self.x, self.y = wx, wy
        else:
            px, py = self.parent.world_pos(cam)
            self.x, self.y = wx - px, wy - py

    def world_rect(self, cam=(0.0, 0.0)):
        x, y = self.world_pos(cam)
        return x - self.w / 2, y - self.h / 2, self.w, self.h

    def iter_tree(self):
        yield self
        for c in self.children:
            yield from c.iter_tree()

    def is_active(self):
        o = self
        while o is not None:
            if not o.active:
                return False
            o = o.parent
        return True

    def matches(self, target):
        """True for the exact name, the name with ' (number)' added, or '#tag' for a tag."""
        if target[:1] == "#":
            return target[1:] in self.tags
        return self.name == target or base_name(self.name) == target
