"""Scene container: the tree of GameObjects plus background settings. Pure python (no Qt)."""
from .gameobject import GameObject, SAVE_FIELDS, KINDS, base_name  # noqa: F401  (re-exported)

SCENE_FORMAT = 1


def sort_for_drawing(scene):
    """Objects in draw order: lower layers first; objects on the same layer keep their hierarchy order."""
    return sorted(scene.all(), key=lambda o: o.layer)


class Scene:
    def __init__(self):
        self.roots = []
        self.bg = "#1f2433"
        self.darkness = 0.0          # 0 = bright, 1 = pitch black (lights cut through it)
        self.ambient = "#0a0c18"     # color of the darkness
        self.joints = []             # ropes, springs and welds that are alive right now (set by the runtime)

    def all(self):
        for r in self.roots:
            yield from r.iter_tree()

    def find_id(self, oid):
        for o in self.all():
            if o.id == oid:
                return o
        return None

    def find_name(self, name):
        for o in self.all():
            if o.name == name:
                return o
        return None

    def camera(self):
        for o in self.all():
            if o.kind == "camera":
                return o
        return None

    def unique_name(self, base):
        names = {o.name for o in self.all()}
        if base not in names:
            return base
        n = 1
        while f"{base} ({n})" in names:
            n += 1
        return f"{base} ({n})"

    def add(self, obj, parent=None, index=None):
        obj.parent = parent
        lst = parent.children if parent else self.roots
        if index is None:
            lst.append(obj)
        else:
            lst.insert(index, obj)
        return obj

    def remove(self, obj):
        lst = obj.parent.children if obj.parent else self.roots
        if obj in lst:
            lst.remove(obj)
        obj.parent = None

    def to_dict(self):
        return {"format": SCENE_FORMAT, "bg": self.bg, "darkness": self.darkness, "ambient": self.ambient, "objects": [r.to_dict() for r in self.roots]}

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.bg = d.get("bg", s.bg)
        dk = d.get("darkness", 0.0)
        s.darkness = max(0.0, min(1.0, float(dk))) if isinstance(dk, (int, float)) and not isinstance(dk, bool) else 0.0
        s.ambient = d.get("ambient", s.ambient) if isinstance(d.get("ambient"), str) else s.ambient
        s.roots = [GameObject.from_dict(o) for o in d.get("objects", [])]
        return s
