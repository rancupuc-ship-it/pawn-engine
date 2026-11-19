"""Game runtime: runs scripts, physics, camera. Pure python (no Qt)."""
import math
import random
import uuid

from pawnlang import Context, PawnError, parse
from . import animation, joints, particles, physics
from .builtins import build_shared
from .gameobject import GameObject, UI_KINDS, base_name
from .modules import ModuleLoader
from .proxies import GameNS, MouseNS, CameraProxy, ObjProxy, GETTERS, METHODS  # noqa: F401  (re-exported)
from .scene import Scene
from .script_instance import ScriptInstance, TaskHost
from .ui import UIController

GAME_SCRIPT = "game.pawn"       # if the project has a script with this name it runs once for the whole game


class Runtime:
    GRAVITY = physics.GRAVITY
    VIEW_W, VIEW_H = 960.0, 540.0

    def __init__(self, scene_dict, project, console=None, play_sound=None, audio=None, scene_name=None):
        self.project = project
        self.scene_name = scene_name or project.start_scene
        self.scene_request = None
        self.break_msg = None
        self.shake_t = self.shake_amp = self.shake_len = 0.0
        self._prefabs = {}
        self._global_insts = []
        self.scene = Scene.from_dict(scene_dict)
        self.joints = []
        self.effects = {}
        self.pads, self.pads_prev = [], []
        self.rumble_fn = None
        self.console = console or (lambda msg, level="print": print(msg))
        self.play_sound = play_sound
        self.audio = audio
        self.ctx = Context(warn=self._warn)
        self.rng = random.Random()
        self.events = {}
        self.game = GameNS()
        self.mouse = MouseNS(self)
        self.camera = CameraProxy(self)
        self.down, self.pressed = set(), set()
        self.mx = self.my = 0.0
        self.mouse_down = False
        self.mouse_clicked = False      # true only on the frame the button went down
        self._prev_mouse_down = False
        self.typed = []                 # characters typed this frame ("\b" = backspace, "\n" = enter)
        self.ui = UIController(self)
        self.time = 0.0
        self.cam = [0.0, 0.0]
        self.cam_obj = self.scene.camera()
        self.programs = {}
        self.instances = []
        self.modules = ModuleLoader(self)
        self.host = TaskHost(self)
        self._live_cache = None
        self._index = {}
        self.restart_requested = False
        self.shared = {}
        self.shared.update(build_shared(self))

    # ---- helpers ------------------------------------------------------------
    def camv(self):
        """Camera centre plus its zoom (the zoom lets screen-anchored UI stay on the screen edges)."""
        return (self.cam[0], self.cam[1], self.cam_obj.zoom if self.cam_obj else 1.0)

    def _warn(self, msg, line, file):
        where = (file or "script") + (f", line {line}" if line else "")
        self.console(f"{where}: {msg}", "warn")

    def get_program(self, file):
        stamp = self.project.script_stamp(file)
        hit = self.programs.get(file)
        if hit is not None and stamp is not None and hit[0] == stamp:
            return hit[1]
        try:
            text = self.project.read_script(file)
        except OSError:
            raise PawnError(f"I can't find the script '{file}'.", hint="was it renamed or deleted?", file=file)
        prog = parse(text, file)
        self.programs[file] = (stamp, prog)
        return prog

    def require(self, name):
        return self.modules.require(name)

    def request_restart(self):
        self.restart_requested = True

    def request_scene(self, name):
        """load_scene("Level 2"): the switch happens at the end of this frame so the running scripts can finish."""
        from pawnlang import suggest
        if not isinstance(name, str):
            raise PawnError('load_scene() needs the name of a scene, like  load_scene("Level 2")')
        if not self.project.scene_exists(name):
            have = self.project.list_scenes()
            raise PawnError(f"I can't find a scene called '{name}'.",
                            hint=suggest(name, have) or ("your scenes: " + ", ".join(have)))
        self.scene_request = name

    def _switch_scene(self, name):
        keep = set(map(id, self._global_insts))
        for inst in self.instances:
            if id(inst) not in keep:
                inst.cancel_all()
        self.instances = [i for i in self.instances if id(i) in keep]
        self.host.tasks = []
        self.host.tweens = {}
        self.scene = Scene.from_dict(self.project.load_scene(name))
        self.joints = []
        self.scene_name = name
        self.cam_obj = self.scene.camera()
        self.ui.reset()
        self.events = {k: v for k, v in self.events.items()}
        self.shake_t = self.shake_amp = 0.0
        self._load_scene_objects()

    def _load_scene_objects(self):
        if self.cam_obj:
            self.cam = list(self.cam_obj.world_pos())
        for r in list(self.scene.roots):
            self.attach_scripts(r)
        self.invalidate()
        for o in self.scene.all():
            animation.autoplay(o)
        starting = [i for i in self.instances if not getattr(i, "_started", False)]
        for inst in starting:
            inst.start()

    # ---- lifecycle ----------------------------------------------------------------
    def attach_scripts(self, obj):
        made = []
        for o in obj.iter_tree():
            for ref in o.scripts:
                prog = self.get_program(ref["file"])
                inst = ScriptInstance(self, o, ref, prog)
                self.instances.append(inst)
                made.append(inst)
        return made

    def start(self):
        if self.cam_obj:
            self.cam = list(self.cam_obj.world_pos())
        if GAME_SCRIPT in self.project.list_scripts():
            holder = GameObject("Game", "empty")
            holder.scripts = [{"file": GAME_SCRIPT, "values": {}}]
            self._global_insts = self.attach_scripts(holder)
        for r in list(self.scene.roots):
            self.attach_scripts(r)
        self.invalidate()
        for o in self.scene.all():
            animation.autoplay(o)
        self.ctx.begin_frame()
        for inst in list(self.instances):
            inst.start()

    def reload_script(self, file):
        """Hot reload after a script or module was saved. Returns how many things were reloaded."""
        if file.endswith(".pawnmod"):
            return self.modules.reload(file)
        prog = parse(self.project.read_script(file), file)
        self.programs[file] = (self.project.script_stamp(file), prog)
        n = 0
        for inst in self.instances:
            if inst.file == file:
                inst.hot_reload(prog)
                n += 1
        return n

    # ---- queries ----------------------------------------------------------------------
    def invalidate(self):
        """Call whenever objects appear, disappear, are tagged or shown/hidden."""
        self._live_cache = None

    def _live(self):
        if self._live_cache is None:
            live, index = [], {}
            for o in self.scene.all():
                if o.dead or not o.is_active():
                    continue
                live.append(o)
                keys = {o.name, base_name(o.name)}
                keys.update("#" + t for t in o.tags)
                for k in keys:
                    index.setdefault(k, []).append(o)
            self._live_cache, self._index = live, index
        return self._live_cache

    def _candidates(self, target):
        if not isinstance(target, str):
            raise PawnError("I need a name (as text) to look for, like  find(\"Player\")  or  all(\"#enemy\").")
        self._live()
        return self._index.get(target, ())

    def find(self, name):
        for o in self._candidates(name):
            return ObjProxy(o, self)
        return None

    def all_named(self, name):
        return [ObjProxy(o, self) for o in self._candidates(name)]

    def touching(self, me, target):
        cam = self.camv()
        mx, my = me.world_pos(cam)
        for o in self._candidates(target):
            if o is me:
                continue
            ox, oy = o.world_pos(cam)
            if physics.overlap(mx, my, me.w, me.h, ox, oy, o.w, o.h):
                return ObjProxy(o, self)
        return None

    def distance(self, a, b):
        if not (isinstance(a, ObjProxy) and isinstance(b, ObjProxy)):
            raise PawnError("distance() needs two objects.", hint='like: distance(self, find("Player"))')
        ax, ay = a.obj.world_pos(self.camv())
        bx, by = b.obj.world_pos(self.camv())
        return math.hypot(ax - bx, ay - by)

    def nearest(self, me, target):
        best, best_d = None, 1e18
        mx, my = me.world_pos(self.camv())
        for o in self._candidates(target):
            if o is me:
                continue
            ox, oy = o.world_pos(self.camv())
            d = math.hypot(ox - mx, oy - my)
            if d < best_d:
                best, best_d = o, d
        return ObjProxy(best, self) if best else None

    def _prefab_copy(self, name):
        """A fresh object tree made from prefabs/<name>.prefab.json, or None if there is no such prefab."""
        stamp = self.project.prefab_stamp(name)
        if stamp is None:
            return None
        hit = self._prefabs.get(name)
        if hit is None or hit[0] != stamp:
            try:
                data = self.project.load_prefab(name)
            except (OSError, ValueError):
                raise PawnError(f"The prefab '{name}' is damaged and can't be read.")
            hit = self._prefabs[name] = (stamp, data)
        c = GameObject.from_dict(hit[1])
        for n in c.iter_tree():
            n.id = uuid.uuid4().hex[:8]
        return c

    def spawn(self, name, x=None, y=None):
        if not isinstance(name, str):
            raise PawnError("spawn() needs the name of an object or prefab, like  spawn(\"Coin\", 100, 50)")
        template = None
        for o in self.scene.all():
            if not o.dead and o.matches(name):
                template = o
                break
        if template is None:
            c = self._prefab_copy(name)
            if c is None:
                have = self.project.list_prefabs()
                raise PawnError(f"I can't find an object or prefab named '{name}' to copy.",
                                hint=("prefabs: " + ", ".join(have)) if have else
                                "make an object (untick Active to use it as a template) or right-click it > Save as prefab")
            parent = None
        else:
            c = template.clone()
            c.name = template.name
            parent = template.parent
        c.active = True
        c.dead = False
        c.vy, c.on_ground = 0.0, False
        self.scene.add(c, parent)
        if x is not None and y is not None:
            if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                raise PawnError("spawn() needs numbers for the position, like  spawn(\"Coin\", 100, 50)")
            c.set_world_pos(float(x), float(y), self.camv())
        self.invalidate()
        for n in c.iter_tree():
            animation.autoplay(n)
        for inst in self.attach_scripts(c):
            inst.start()
        return ObjProxy(c, self)

    def destroy(self, target):
        if target is None:
            return
        if not isinstance(target, (ObjProxy, GameObject)):
            raise PawnError("destroy() needs an object, like  destroy(coin)  or  self.destroy()")
        obj = target.obj if isinstance(target, ObjProxy) else target
        for n in obj.iter_tree():
            n.dead = True
        self.invalidate()

    # ---- frame ----------------------------------------------------------------------------
    def update(self, dt):
        self.ctx.begin_frame()
        self.time += dt
        self.shared["dt"] = dt
        self.mouse_clicked = self.mouse_down and not self._prev_mouse_down
        self.ui.update()
        self._prev_mouse_down = self.mouse_down
        bodies = [o for o in self._live() if o.body and o.parent is None]
        prev = {id(b): b.world_pos() for b in bodies}
        if self.audio is not None and hasattr(self.audio, "tick"):
            self.audio.tick(dt)
        self.host.update(dt)
        for inst in list(self.instances):
            if inst.obj.dead or not inst.obj.is_active():
                continue
            inst.tick(dt)
        physics.step(self._live(), bodies, prev, dt)
        if self.joints:
            joints.solve(self.joints, dt)
            self.scene.joints = self.joints
        self._touch_events()
        self._prompts()
        for o in self._live():
            if o.anim_name:
                animation.advance(o, dt)
            if o.kind == "particles" and (o.parts or o.em_on):
                particles.update(o, dt, self.rng)
        self._camera(dt)
        self._flush()
        if self.scene_request is not None:
            name, self.scene_request = self.scene_request, None
            self.ctx.begin_frame()
            self._switch_scene(name)
        self.pressed.clear()
        self.typed.clear()

    def _touch_events(self):
        """Fire  on touch / on untouch  for objects whose scripts have those blocks (triggers, pickups, hazards)."""
        watchers = [i for i in self.instances if ("touch" in i.event_bodies or "untouch" in i.event_bodies)
                    and not i.obj.dead and i.obj.is_active()]
        if not watchers:
            return
        cam = self.camv()
        cell = 128.0
        grid = {}
        for o in self._live():
            if o.kind in ("camera", "empty", "model", "folder", "spawn", "beam", "prompt") or o.kind in UI_KINDS:
                continue
            x, y = o.world_pos(cam)
            hw, hh = o.w / 2, o.h / 2
            for gx in range(int((x - hw) // cell), int((x + hw) // cell) + 1):
                for gy in range(int((y - hh) // cell), int((y + hh) // cell) + 1):
                    grid.setdefault((gx, gy), []).append((o, x, y))
        for inst in watchers:
            me = inst.obj
            mx, my = me.world_pos(cam)
            now = {}
            for gx in range(int((mx - me.w / 2) // cell), int((mx + me.w / 2) // cell) + 1):
                for gy in range(int((my - me.h / 2) // cell), int((my + me.h / 2) // cell) + 1):
                    for o, ox, oy in grid.get((gx, gy), ()):
                        if o is me or id(o) in now or o.parent is me or me.parent is o or not me.collides_with(o):
                            continue
                        if physics.overlap(mx, my, me.w, me.h, ox, oy, o.w, o.h):
                            now[id(o)] = o
            before = getattr(inst, "touched", {})
            inst.touched = now
            for k, o in now.items():
                if k not in before and not me.dead:
                    inst.fire_event("touch", ObjProxy(o, self))
            for k, o in before.items():
                if k not in now and not me.dead:
                    inst.fire_event("untouch", ObjProxy(o, self))

    def _prompts(self):
        """Proximity prompts: show the bubble when a #player is close, and run  on prompt  when E (or pad X) is pressed."""
        prompts = [o for o in self._live() if o.kind == "prompt"]
        if not prompts:
            return
        players = self.all_named("#player")
        pressed = "e" in self.pressed or any("x" in st["buttons"] and "x" not in (self.pads_prev[i]["buttons"] if i < len(self.pads_prev) else ())
                                             for i, st in enumerate(self.pads))
        for o in prompts:
            ox, oy = o.world_pos()
            r = max(8.0, o.w / 2)
            near = None
            for pl in players:
                px, py = pl.obj.world_pos()
                if (px - ox) ** 2 + (py - oy) ** 2 <= r * r:
                    near = pl
                    break
            o.focused = near is not None
            if near is not None and pressed:
                for inst in list(self.instances):
                    if inst.obj is o and not o.dead:
                        inst.fire_event("prompt", near)

    def spawn_point(self, name=None):
        pts = [o for o in self._live() if o.kind == "spawn" and (name is None or o.name == name or base_name(o.name) == name)]
        return ObjProxy(pts[0], self) if pts else None

    def respawn(self, who, point=None):
        """Put an object back at a spawn point (the first one, or the named one) and stop it moving."""
        if not hasattr(who, "obj"):
            raise PawnError("respawn() needs an object, like  respawn(self)")
        sp = self.spawn_point(point if isinstance(point, str) else (point.obj.name if hasattr(point, "obj") else None))
        if sp is None:
            raise PawnError("There is no spawn point in this scene.", hint="add one from Object > Add > Spawn point")
        x, y = sp.obj.world_pos()
        who.obj.set_world_pos(x, y)
        who.obj.vx = who.obj.vy = 0.0

    def set_pads(self, states):
        """Called every frame by the window with the state of each connected controller."""
        self.pads_prev = self.pads
        self.pads = states

    def pad_state(self, index):
        if isinstance(index, bool) or not isinstance(index, int) or index < 1:
            raise PawnError("The pad number must be 1, 2, 3 or 4.")
        return self.pads[index - 1] if index <= len(self.pads) else None

    def _camera(self, dt):
        c = self.cam_obj
        if c is None or c.dead:
            return
        if c.follow:
            target = next(iter(self._candidates(c.follow)), None)
            if target is not None:
                tx, ty = target.world_pos()
                cx, cy = c.world_pos()
                k = min(1.0, 8.0 * dt)
                c.set_world_pos(cx + (tx - cx) * k, cy + (ty - cy) * k)
        self.cam = list(c.world_pos())
        if self.shake_t > 0:
            self.shake_t = max(0.0, self.shake_t - dt)
            k = self.shake_amp * (self.shake_t / max(0.001, self.shake_len))
            self.cam[0] += (self.rng.random() * 2 - 1) * k
            self.cam[1] += (self.rng.random() * 2 - 1) * k

    def shake(self, amount=8, seconds=0.3):
        self.shake_amp = max(0.0, min(200.0, float(amount)))
        self.shake_t = self.shake_len = max(0.0, min(10.0, float(seconds)))

    def _flush(self):
        dead = [o for o in self.scene.all() if o.dead]
        for o in dead:
            if o.parent is not None or o in self.scene.roots:
                lst = o.parent.children if o.parent else self.scene.roots
                if o in lst:
                    lst.remove(o)
        if dead:
            gone = [i for i in self.instances if i.obj.dead]
            for i in gone:
                i.cancel_all()
            self.instances = [i for i in self.instances if not i.obj.dead]
            self.invalidate()
