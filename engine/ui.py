"""Mouse and keyboard handling for UI objects (buttons, sliders, checkboxes, text boxes) and clickable objects."""
from .gameobject import UI_KINDS

MAX_TEXT = 200


class UIController:
    def __init__(self, rt):
        self.rt = rt
        self.hover = None
        self.pressed = None
        self.focus = None
        self.prev_down = False

    def reset(self):
        """A new scene was loaded: forget everything that pointed at the old one."""
        self.hover = self.pressed = self.focus = None

    # ---- helpers --------------------------------------------------------------------
    def _clickables(self):
        """UI objects, plus any object with an 'on click'-style block in one of its scripts."""
        seen, out = set(), []
        for inst in self.rt.instances:
            if inst.event_bodies and id(inst.obj) not in seen and not inst.obj.dead and inst.obj.is_active():
                seen.add(id(inst.obj))
                out.append(inst.obj)
        for o in self.rt._live():
            if o.kind in UI_KINDS and id(o) not in seen:
                seen.add(id(o))
                out.append(o)
        out = [o for o in out if o.enabled]
        order = {id(o): i for i, o in enumerate(self.rt._live())}
        out.sort(key=lambda o: (o.layer, order.get(id(o), 0)))
        return out

    def _hit(self, objs, mx, my):
        cam = self.rt.camv()
        for o in reversed(objs):            # topmost first
            x, y = o.world_pos(cam)
            if abs(mx - x) * 2 <= o.w and abs(my - y) * 2 <= o.h:
                return o
        return None

    def _fire(self, obj, name, value=None):
        for inst in list(self.rt.instances):
            if inst.obj is obj:
                inst.fire_event(name, value)

    def _set_focus(self, obj):
        if self.focus is obj:
            return
        if self.focus is not None:
            self.focus.focused = False
        self.focus = obj
        if obj is not None:
            obj.focused = True

    def _forget(self, o):
        return o is not None and (o.dead or not o.is_active() or not o.enabled)

    def _drag(self, slider, mx):
        x, _ = slider.world_pos(self.rt.camv())
        v = max(0.0, min(1.0, (mx - (x - slider.w / 2)) / max(1.0, slider.w)))
        if abs(v - slider.value) > 1e-9:
            slider.value = v
            self._fire(slider, "change", v)

    # ---- per frame ----------------------------------------------------------------------
    def update(self):
        rt = self.rt
        for name in ("hover", "pressed", "focus"):
            o = getattr(self, name)
            if self._forget(o):
                o.hovered = o.pressing = o.focused = False
                setattr(self, name, None)
        mx, my, down = rt.mx, rt.my, rt.mouse_down
        objs = self._clickables()
        top = self._hit(objs, mx, my)
        if top is not self.hover:
            if self.hover is not None:
                self.hover.hovered = False
                self._fire(self.hover, "leave")
            self.hover = top
            if top is not None:
                top.hovered = True
                self._fire(top, "hover")
        if down and not self.prev_down:
            if top is not None:
                self.pressed = top
                top.pressing = True
                self._set_focus(top if top.kind == "input" else None)
                self._fire(top, "press")
                if top.kind == "slider":
                    self._drag(top, mx)
            else:
                self._set_focus(None)
        elif down and self.pressed is not None and self.pressed.kind == "slider":
            self._drag(self.pressed, mx)
        if not down and self.prev_down and self.pressed is not None:
            p, self.pressed = self.pressed, None
            p.pressing = False
            self._fire(p, "release")
            if top is p:
                if p.kind == "checkbox":
                    p.checked = not p.checked
                    self._fire(p, "change", p.checked)
                self._fire(p, "click")
        self.prev_down = down
        self._type()

    def _type(self):
        rt, f = self.rt, self.focus
        if f is None or f.kind != "input" or not rt.typed:
            return
        before = f.text
        for ch in rt.typed:
            if ch == "\b":
                f.text = f.text[:-1]
            elif ch == "\n":
                self._fire(f, "submit", f.text)
            elif ch.isprintable() and len(f.text) < MAX_TEXT:
                f.text += ch
        if f.text != before:
            self._fire(f, "change", f.text)

    def over_ui(self):
        return self.hover is not None
