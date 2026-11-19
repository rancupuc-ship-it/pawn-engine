"""The main editor window: hierarchy, scene view, inspector, code tabs, project files, console."""
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                               QSizePolicy, QTabBar, QTabWidget, QToolBar, QVBoxLayout, QWidget)

from pawnlang import PawnError
from engine.export import export_game
from engine.project import NEW_MODULE, NEW_SCRIPT, PRESETS, IMAGE_EXT, SOUND_EXT, FONT_EXT, add_recent
from engine.render import Assets
from engine.scene import GameObject, Scene
from .codeedit import CodeTab
from .gameview import GameView
from .inspector import Inspector
from .panels import ConsolePanel, HierarchyTree, ProjectPanel
from .sceneview import SceneView
from .watch import WatchPanel
from .theme import C, icon, mono_font

KIND_LABEL = {"rect": "Rectangle", "circle": "Circle", "sprite": "Picture", "text": "Text", "empty": "Empty object",
              "camera": "Camera", "button": "Button", "bar": "Progress bar", "slider": "Slider",
              "checkbox": "Checkbox", "input": "Text box", "polygon": "Polygon", "tilemap": "Tile map", "particles": "Particles", "light": "Light",
              "model": "Model", "folder": "Folder", "zone": "Zone", "spawn": "Spawn point", "beam": "Beam", "prompt": "Prompt"}
HELPER_KINDS = ("model", "folder", "zone", "spawn", "beam", "prompt")
# ready-made Roblox-style parts: label -> (kind, settings)
PARTS = {"Part": ("rect", {"solid": True, "color": "#8a91a3"}),
         "Ball": ("circle", {"body": True, "bounce": 0.6, "color": "#ef6b6b", "solid": False}),
         "Platform": ("rect", {"solid": True, "one_way": True, "color": "#6bd38a", "w": 160, "h": 24}),
         "Ramp": ("rect", {"solid": True, "slope": "up-right", "color": "#c792ea", "w": 160, "h": 80}),
         "Crate": ("rect", {"solid": True, "body": True, "color": "#c9a26a", "w": 60, "h": 60})}
BASIC_KINDS = ("rect", "circle", "sprite", "polygon", "tilemap", "particles", "light", "text", "empty", "camera")
UI_ADD = ("button", "bar", "slider", "checkbox", "input")

GUIDE = '''PAWN QUICK GUIDE
=================

Scripts belong to objects. "self" is the object the script is on.

    speed = 200                         a variable (it shows up in the Inspector)

    on start                            runs once when the game begins
        print("Hello!")

    when key("right")                   runs every frame while this is true
        self.x = self.x + speed * dt    (dt = time since the last frame)

    when pressed("space")               true only on the frame the key goes down
        self.jump(600)

    when touching("Coin") as coin       "as" gives a name to what was touched
        coin.destroy()

    every 2 seconds                     repeats
        spawn("Enemy", 300, 0)

    after 5 seconds                     runs once, later
        print("Five seconds passed")


Ideas        if / elif / else      repeat 3 times      while ...
             each item in list     def name(a, b)  +  return

Objects      x  y  width  height  angle  color  text  visible
             move(dx, dy)  jump(power)  destroy()  hide()  show()
             touching("Name")  distance_to(other)

Finding      find("Player")   all("Coin")   nearest("Coin")   distance(a, b)
             spawn("Name", x, y) copies an object (untick Active to make a template)

Shared       game.score = game.score + 1       (values you never set start at 0)
Text         "Score: {game.score}"             {anything} inside quotes is filled in
Input        key("a")  pressed("space")  mouse.x  mouse.y  mouse.down
Other        random(1, 5)  random_int(1, 6)  round  floor  abs  min  max
             clamp  lerp  sin  cos  sqrt  len  play("coin")  restart()
Camera       camera.x  camera.y  camera.zoom   (or use Follow on the Camera object)

Tip: variables whose names start with _ stay private and are not shown in the Inspector.


NEW IN 1.1
----------
    a = x ?? 5                  use 5 if x is none          can_use("dash", 1.5)   cooldown       wait_left("dash")
    find_path(x1, y1, x2, y2)   A* route                    raycast(x, y, dx, dy)  what a line hits   can_see(a, b)
    rope(a, b)  spring(a, b)  weld(a, b)                    effect("shake", 0.5)   screen effects
    pad("a")  pad_axis("lx")  pad_rumble(0.5)               gamepads
    respawn(self)   spawn_point()                           Add > Helpers: Model, Folder, Zone, Spawn point, Beam, Prompt
    on prompt as who            runs when a #player presses E near a Prompt object

NEW IN 1.0
Game window    Project > Game window: title, size, resizable, fullscreen. assets/icon.png = your own icon
Slimmer exe    build_exe.bat leaves out unused Qt parts, so the app and exported games are smaller

NEW IN 0.5
==========

Helpers        The code editor suggests words as you type (Tab or Enter accepts, after  self.  you get the object's words).
               Click a word to see how it works. Wavy yellow lines are tips: typos like  speeed  or  self.xx.
Inspector      speed = 260   # range 0 600           becomes a slider      (also  # range 0 600 step 10)
               mode = "easy" # choice easy, hard     becomes a drop-down
               tint = "#ff0000" # color              becomes a color button
               hp = 3        # Starting health      any other comment becomes the tooltip
Debugging      breakpoint("note")         pauses the game and opens the Watch panel (bottom tabs)
               Watch panel                shows  game  and the selected object's variables; double-click a value to change it
                                          while playing. F6 continues, the step button moves one frame.
Gallery        Project > Script gallery (or Add script > Gallery): 40+ ready-made scripts you can read and change.
Templates      New project > "Menu and level": a title screen, a tile-map level, a goal and a volume slider.
Lighting       Add > Light, Project > Scene lighting…        darkness(0.7)    ambient("#101030")    light.intensity  light.radius
Parallax       Inspector > Look > Parallax:  1 moves with the world, 0.5 half as fast, 0 stays on screen
Text           "hello".slice(1, 3)

NEW IN 0.4
==========

Scenes         The Scene box in the toolbar switches scenes; Project > New scene makes one.
               load_scene("Level 2")      switches at the end of the frame; "game" data and game.pawn carry over
               scene_name()               Project > Make this scene the first one picks where the game starts
Saving         save_game("slot1")         saves everything in  game  (numbers, text, lists, tables; names with _ are skipped)
               load_game("slot1")         true if found     has_save("slot1")  delete_save("slot1")  saves()
Prefabs        Right-click an object > Save as prefab.     spawn("Coin", x, y) finds scene objects first, then prefabs
Platforms      One-way platform (jump up through it), Slope (ramps), Trigger (not solid), Group + Hits (8 collision groups)
               on touch as who            a trigger or pickup: who is the object that came in
               on untouch as who          it left
               self.trigger  self.one_way  self.solid  self.cgroup  self.cmask
Tile maps      Add > Tile map. Pick a tile sheet, tick "Paint in the Scene": click = paint, Ctrl+click = erase.
               map.set_tile(col, row, n)  map.get_tile(col, row)  map.tile_at(x, y)  map.clear_tiles()
               map.fill_tiles("#..#", {"#": 1})     tiles can be solid
Particles      Add > Particles.   fx.burst(30)    fx.emitting = false
Shake          shake(8, 0.3)      or  camera.shake(8, 0.3)
Polygons       Add > Polygon, or Project > Import SVG drawing (curves, arcs and circles are flattened into polygons)

NEW IN 0.3
==========

Sprite sheets  Pick a Picture, set Columns and Rows in the Inspector, then name clips:
               run = 0-3 @ 10 loop        jump = 4-6 @ 8 once
               self.play_anim("run")      self.stop_anim()      self.frame = 2      self.anim   self.playing
Fonts          Import a .ttf or .otf, then pick it on any Text or UI object (or in Project > UI theme)
Sliding        self.vx = 300              sideways speed.  Inspector: Friction (0 slides forever), Bounce (0 to 1)
               self.push(dx, dy)          a quick shove
Sound          play("coin", 0.5)          play_music("theme", true, 0.7)       volume("music", 0.4)
               fade_music(0, 2, true)     pause_music()  resume_music()  mute()  music_playing()
               Project > Audio mixer sets the starting volumes
UI             Add > UI: Button, Progress bar, Slider, Checkbox, Text box. They stay on screen (pick an Anchor).
               on click / press / release / hover / leave      in a script on the UI object
               on change as v             sliders, checkboxes and text boxes give you the new value
               on submit as text          Enter in a text box
               self.value (bar, slider)   self.checked   self.text   self.enabled   typing()   over_ui()
               Project > UI theme         colors, roundness and font for all of them
Mouse          mouse.clicked              true on the frame the button went down

NEW IN 0.2
==========

Variables      local n = 0               a private variable (not shown in the Inspector, remembered between runs
                                         when written at the top of a script; temporary inside when / every)
Tables         t = {hp = 3, name = "orc"}      t.hp += 1      t["mp"] = 5      t.has("hp")
               each k, v in pairs(t)     each i, x in list      keys(t)  values(t)  range(5)  sorted(list)
Lists          add  remove  pop  insert(i, x)  sort()  reverse()  slice(a, b)  join(", ")  index_of(x)
Maths          2 ^ 3  (power)     7 // 2  (whole-number divide)     seed(7) makes random() repeatable

Waiting        wait 2 seconds            pause this block (the game keeps running)
               wait until game.ready     wait frame      wait tweens
               A 'when' block that is still waiting does not start again on top of itself.
Tweens         tween self.x to 300 over 1 second ease out      (ease: linear, in, out, inout, smooth)
Signals        hit = signal()     hit.connect(my_function)     hit.fire(5)     hit.once(f)     hit.wait()
               event("boom") is a signal shared by name between every script
Watch          watch game.score as s        runs its block each time the value changes ("old" = the previous value)
States         state idle                   a little machine: only the current state's blocks run
                   on enter / on exit / when / every / after / watch
                   when key("space")
                       go jump              switch state (the block ends there)
               current_state()   in_state("jump")
Tags           self.tag("enemy")     all("#enemy")     tagged("enemy")     touching("#enemy")
Pictures       self.sprite = "assets/sprites/hero.png"    self.flip_x = true    self.alpha = 0.5    self.layer = 3
Sound          play("coin")     play_music("theme")     stop_music()     volume("music", 0.5)     volume(0.8)

Module scripts (＋ New module in the Project panel) hold shared code. They run once and must end with return:
    tools = require("tools")           then   tools.double(4)
A script called game.pawn runs once for the whole game (good for score, levels and rules).
'''


def ui_defaults(o):
    """Starting size and text for a freshly added UI object. UI objects stay on screen (anchored) by default."""
    o.hud = True
    o.color = ""          # empty = follow the project's UI theme
    o.text_size = 22
    k = o.kind
    if k == "button":
        o.w, o.h, o.text = 200, 54, "Button"
    elif k == "bar":
        o.w, o.h, o.value, o.text = 300, 24, 0.7, ""
    elif k == "slider":
        o.w, o.h, o.value, o.text = 300, 24, 0.5, ""
    elif k == "checkbox":
        o.w, o.h, o.text, o.checked = 240, 32, "Option", False
    elif k == "input":
        o.w, o.h, o.text = 300, 48, ""
    o.anchor = "center"


SHAPES = {
    "triangle": [[0, -0.5], [0.5, 0.5], [-0.5, 0.5]],
    "diamond": [[0, -0.5], [0.5, 0], [0, 0.5], [-0.5, 0]],
    "hexagon": [[-0.25, -0.5], [0.25, -0.5], [0.5, 0], [0.25, 0.5], [-0.25, 0.5], [-0.5, 0]],
    "star": [[0, -0.5], [0.12, -0.17], [0.48, -0.15], [0.19, 0.07], [0.3, 0.45], [0, 0.22], [-0.3, 0.45], [-0.19, 0.07],
             [-0.48, -0.15], [-0.12, -0.17]],
    "arrow": [[-0.5, -0.15], [0.1, -0.15], [0.1, -0.5], [0.5, 0], [0.1, 0.5], [0.1, 0.15], [-0.5, 0.15]],
}


def shape_points(name):
    return [list(p) for p in SHAPES[name]]


class EditorWindow(QMainWindow):
    back_to_menu = Signal()

    def __init__(self, project):
        super().__init__()
        self.setAcceptDrops(True)
        self.project = project
        self.scene_name = project.start_scene
        self.scene = Scene.from_dict(project.load_scene(self.scene_name))
        self.assets = Assets(project.path)
        self.assets.theme = project.theme
        self.selected = None
        self.tile_brush, self.tile_paint = 0, False
        self.undo_stack, self.redo_stack = [], []
        self._last_key, self._last_t = None, 0.0
        self._to_menu = False
        self.setWindowTitle(f"{project.name} — Pawn Engine")
        self.resize(1380, 840)

        self.console = ConsolePanel()
        self.scene_view = SceneView(self)
        self.game_view = GameView(project, self.assets, self.log)
        self.inspector = Inspector(self)
        self.tree = HierarchyTree()
        self.files = ProjectPanel()

        self._build_central()
        self._build_docks()
        self._build_toolbar()
        self._build_menus()
        self._wire()

        self.watch_timer = QTimer(self, interval=250)
        self.watch_timer.timeout.connect(self._refresh_watch)
        self.watch_timer.start()
        self.save_timer = QTimer(self, singleShot=True, interval=700)
        self.save_timer.timeout.connect(self.save_scene)

        self.files.refresh(project)
        self.rebuild_hierarchy()
        first = self.scene.find_name("Player") or (self.scene.roots[0] if self.scene.roots else None)
        self.select(first)
        self.statusBar().showMessage("Ready")
        self.saved_label = QLabel("Auto-saved")
        self.statusBar().addPermanentWidget(self.saved_label)
        add_recent(project)
        QTimer.singleShot(0, self.scene_view.fit_all)
        self.log("Welcome to Pawn Engine! Press ▶ Play to run your game. Help ▸ Pawn quick guide explains the language.", "info")

    # ====================================================== layout
    def _build_central(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.banner = QFrame()
        self.banner.setProperty("banner", "error")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(14, 8, 10, 8)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_show = QPushButton("Show the line")
        self.banner_go = QPushButton("Continue")
        self.banner_go.setProperty("primary", True)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(self.banner_show)
        bl.addWidget(self.banner_go)
        self.banner.hide()
        mw = QWidget()
        mw.setObjectName("bannerWrap")
        mwl = QVBoxLayout(mw)
        mwl.setContentsMargins(8, 8, 8, 0)
        mwl.addWidget(self.banner)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.scene_view, icon("rect", C["gold"], 16), "Scene")
        self.tabs.addTab(self.game_view, icon("play", C["teal"], 16), "Game")
        v.addWidget(mw)
        mw.setStyleSheet("#bannerWrap { background: %s; }" % C["bg0"])
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(wrap)

    def _dock(self, title, widget, area):
        d = QDockWidget(title, self)
        d.setFeatures(QDockWidget.NoDockWidgetFeatures)
        d.setWidget(widget)
        d.setTitleBarWidget(None)
        self.addDockWidget(area, d)
        return d

    def _build_docks(self):
        hier = QWidget()
        hl = QVBoxLayout(hier)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(10, 8, 10, 4)
        add = QPushButton("＋ Add object")
        add.setProperty("primary", True)
        add.clicked.connect(lambda: self._add_menu(add))
        top.addWidget(add)
        top.addStretch(1)
        hl.addLayout(top)
        self.tree_search = QLineEdit()
        self.tree_search.setPlaceholderText("Search objects…")
        self.tree_search.setClearButtonEnabled(True)
        self.tree_search.addAction(icon("search", C["muted"], 14), QLineEdit.LeadingPosition)
        self.tree_search.textChanged.connect(self.tree.set_filter)
        sw = QHBoxLayout()
        sw.setContentsMargins(10, 2, 10, 6)
        sw.addWidget(self.tree_search)
        hl.addLayout(sw)
        hl.addWidget(self.tree, 1)
        self.dock_h = self._dock("Hierarchy", hier, Qt.LeftDockWidgetArea)
        props = QWidget()
        pl = QVBoxLayout(props)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        self.prop_search = QLineEdit()
        self.prop_search.setPlaceholderText("Search properties…")
        self.prop_search.setClearButtonEnabled(True)
        self.prop_search.addAction(icon("search", C["muted"], 14), QLineEdit.LeadingPosition)
        self.prop_search.textChanged.connect(self.inspector.set_search)
        sw2 = QHBoxLayout()
        sw2.setContentsMargins(10, 8, 10, 2)
        sw2.addWidget(self.prop_search)
        pl.addLayout(sw2)
        pl.addWidget(self.inspector, 1)
        self.dock_i = self._dock("Properties", props, Qt.RightDockWidgetArea)
        bottom = QTabWidget()
        bottom.addTab(self.files, icon("script", C["purple"], 16), "Project")
        bottom.addTab(self.console, "Console")
        self.watch = WatchPanel(self)
        bottom.addTab(self.watch, "Watch")
        self.bottom_tabs = bottom
        self.dock_b = self._dock("Project and Console", bottom, Qt.BottomDockWidgetArea)
        self.dock_b.setTitleBarWidget(QWidget())
        self.resizeDocks([self.dock_h, self.dock_i], [250, 360], Qt.Horizontal)
        self.resizeDocks([self.dock_b], [170], Qt.Vertical)

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)
        title = QLabel(self.project.name)
        title.setStyleSheet(f"color: {C['text']}; font-weight: 700; font-size: 14px;")
        tb.addWidget(title)
        gap = QLabel("   Scene ")
        gap.setProperty("muted", True)
        tb.addWidget(gap)
        self.scene_combo = QComboBox()
        self.scene_combo.setMinimumWidth(150)
        self.scene_combo.setToolTip("Switch between the scenes (levels, menus...) of your game")
        tb.addWidget(self.scene_combo)
        self._fill_scene_combo()
        self.scene_combo.activated.connect(self._scene_combo_picked)
        sp = QWidget()
        sp.setStyleSheet("background: transparent;")
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp)
        self.btn_play = QPushButton("  Play")
        self.btn_play.setProperty("play", True)
        self.btn_play.setIcon(icon("play", "#ffffff", 16))
        self.btn_pause = QPushButton()
        self.btn_pause.setIcon(icon("pause", C["text"], 16))
        self.btn_pause.setToolTip("Pause / resume")
        self.btn_step = QPushButton()
        self.btn_step.setIcon(icon("step", C["text"], 16))
        self.btn_step.setToolTip("Advance one frame (while paused)")
        for b in (self.btn_play, self.btn_pause, self.btn_step):
            tb.addWidget(b)
        sp2 = QWidget()
        sp2.setStyleSheet("background: transparent;")
        sp2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp2)
        hint = QLabel("Everything saves automatically")
        tb.addWidget(hint)
        self.on_game_state()

    def _act(self, menu, text, fn, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(lambda _=False: fn())
        menu.addAction(a)
        return a

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        self._act(m, "Save everything", self.save_all, "Ctrl+S")
        self._act(m, "Export game…", self.export, "Ctrl+E")
        self._act(m, "Show project folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.path))))
        m.addSeparator()
        self._act(m, "Back to main menu", self.close_to_menu, "Ctrl+W")
        self._act(m, "Quit", QApplication.quit, "Ctrl+Q")
        m = mb.addMenu("&Edit")
        self._act(m, "Undo", self.do_undo, "Ctrl+Z")
        self._act(m, "Redo", self.do_redo, "Ctrl+Y")
        m.addSeparator()
        self._act(m, "Duplicate", self.duplicate_selected, "Ctrl+D")
        self._act(m, "Delete", self.delete_selected)
        m = mb.addMenu("&Object")
        add = m.addMenu("Add")
        for k in BASIC_KINDS:
            self._act(add, KIND_LABEL[k], lambda k=k: self.add_object(k))
        uim = add.addMenu("UI")
        for k in UI_ADD:
            self._act(uim, KIND_LABEL[k], lambda k=k: self.add_object(k))
        pm = add.addMenu("Parts")
        for label in PARTS:
            self._act(pm, label, lambda label=label: self.add_part(label))
        hm = add.addMenu("Helpers")
        for k in HELPER_KINDS:
            self._act(hm, KIND_LABEL[k], lambda k=k: self.add_object(k))
        vm = mb.addMenu("&View")
        self._act(vm, "Dark theme", lambda: self.set_theme("dark"))
        self._act(vm, "Light theme", lambda: self.set_theme("light"))
        self._act(vm, "Toggle theme", lambda: self.set_theme("dark" if self.theme_mode == "light" else "light"), "Ctrl+Shift+T")
        m = mb.addMenu("&Project")
        self._act(m, "New scene…", self.new_scene)
        self._act(m, "Make this scene the first one", self.make_start_scene)
        self._act(m, "Delete this scene…", self.delete_scene_dialog)
        m.addSeparator()
        self._act(m, "Scene lighting…", self.edit_lighting)
        self._act(m, "UI theme…", self.edit_theme)
        self._act(m, "Audio mixer…", self.edit_mixer)
        self._act(m, "Game window…", self.edit_window)
        self._act(m, "Import picture, sound or font…", self.import_assets)
        self._act(m, "Import SVG drawing…", self.import_svg)
        self._act(m, "Script gallery…", self.open_gallery)
        m = mb.addMenu("&Game")
        self._act(m, "Play / Stop", self.play, "F5")
        self._act(m, "Pause / Resume", self.game_view.toggle_pause, "F6")
        self._act(m, "Next frame", self.game_view.step, "F10")
        m = mb.addMenu("&Help")
        self._act(m, "Pawn quick guide", self.show_guide, "F1")
        self._act(m, "Check for updates", lambda: self.check_updates(True))
        self._act(m, "About Pawn Engine", self.about)

    def _wire(self):
        self.scene_view.selected.connect(self.select)
        self.game_view.break_hit.connect(self._on_break)
        self.scene_view.transformed.connect(self._on_transform)
        self.scene_view.finished.connect(self._on_transform_done)
        self.tree.picked.connect(lambda oid: self.select(self.scene.find_id(oid) if oid else None, from_tree=True))
        self.tree.renamed.connect(self._renamed)
        self.tree.about_to_reorder.connect(lambda: self.checkpoint(force=True))
        self.tree.reordered.connect(self.sync_from_tree)
        self.tree.menu_requested.connect(self._tree_menu)
        self.tree.flag_toggled.connect(self._flag_toggled)
        QShortcut(QKeySequence(Qt.Key_Delete), self.tree, activated=self.delete_selected).setContext(Qt.WidgetShortcut)
        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self.game_view.toggle_pause)
        self.btn_step.clicked.connect(self.game_view.step)
        self.game_view.state_changed.connect(self.on_game_state)
        self.game_view.error_raised.connect(self.on_game_error)
        self.banner_go.clicked.connect(self._continue)
        self.banner_show.clicked.connect(self._show_error_line)
        self.files.open_script.connect(self.open_script)
        self.files.attach_script.connect(lambda f: self._attach_to_selected(f))
        self.files.use_sprite.connect(self.use_sprite)
        self.files.add_prefab.connect(self.add_prefab)
        self.files.new_script.connect(self.new_script)
        self.files.new_module.connect(self.new_module)
        self.files.files_dropped.connect(self.import_paths)
        self.files.import_asset.connect(self.import_assets)
        self.files.delete_file.connect(self.delete_file)
        self._last_error = None

    # ====================================================== logging / state
    def log(self, msg, level="print"):
        self.console.log(msg, level)

    def mark_dirty(self):
        self.saved_label.setText("Saving…")
        self.save_timer.start()

    def save_scene(self):
        self.project.save_scene(self.scene.to_dict(), self.scene_name)
        self.saved_label.setText("Auto-saved ✓")

    def _on_break(self):
        self.bottom_tabs.setCurrentWidget(self.watch)
        self.watch.refresh(self.game_view.rt, self.selected)

    def _refresh_watch(self):
        gv = self.game_view
        if gv.running and self.bottom_tabs.currentWidget() is self.watch:
            self.watch.refresh(gv.rt, self.selected)
        elif not gv.running and self.watch.rt is not None:
            self.watch.clear()

    # ====================================================== scenes
    def _fill_scene_combo(self):
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        for n in self.project.list_scenes():
            self.scene_combo.addItem(n + ("  ★" if n == self.project.start_scene else ""), n)
        self.scene_combo.addItem("＋ New scene…", None)
        self.scene_combo.setCurrentIndex(max(0, self.scene_combo.findData(self.scene_name)))
        self.scene_combo.blockSignals(False)

    def _scene_combo_picked(self, i):
        name = self.scene_combo.itemData(i)
        if name is None:
            self.new_scene()
        else:
            self.switch_scene(name)

    def switch_scene(self, name):
        if name == self.scene_name or not self.project.scene_exists(name):
            self._fill_scene_combo()
            return
        if self.game_view.running:
            self.stop()
        self.save_scene()
        self.scene_name = name
        self.scene = Scene.from_dict(self.project.load_scene(name))
        self.undo_stack, self.redo_stack = [], []
        self.selected = None
        self.rebuild_hierarchy()
        first = self.scene.roots[0] if self.scene.roots else None
        self.select(first)
        self._fill_scene_combo()
        self.scene_view.fit_all()
        self.statusBar().showMessage(f"Editing scene: {name}", 3000)

    def new_scene(self):
        name, ok = QInputDialog.getText(self, "New scene", "Name of the new scene:", text=self.project.new_scene_name("Level"))
        name = name.strip() if ok else ""
        if not name:
            self._fill_scene_combo()
            return
        name = self.project.new_scene_name(name) if self.project.scene_exists(name) else name
        try:
            self.project.scene_path(name)
        except ValueError as e:
            QMessageBox.warning(self, "New scene", str(e))
            self._fill_scene_combo()
            return
        cam = GameObject("Main Camera", "camera")
        cam.w, cam.h = 60, 40
        cam.color = "#f2b84b"
        fresh = Scene()
        fresh.add(cam)
        self.project.save_scene(fresh.to_dict(), name)
        self.switch_scene(name)
        self.log(f"Made scene '{name}'. Use  load_scene(\"{name}\")  in a script to go there.", "ok")

    def delete_scene_dialog(self):
        if len(self.project.list_scenes()) <= 1:
            QMessageBox.information(self, "Delete scene", "A game needs at least one scene.")
            return
        name = self.scene_name
        if QMessageBox.question(self, "Delete scene", f"Delete the scene '{name}'? This can't be undone.") != QMessageBox.Yes:
            return
        if self.game_view.running:
            self.stop()
        self.save_timer.stop()
        self.project.delete_scene(name)
        other = self.project.start_scene
        self.scene = Scene.from_dict(self.project.load_scene(other))
        self.scene_name = other
        self.undo_stack, self.redo_stack = [], []
        self.selected = None
        self.rebuild_hierarchy()
        self.select(self.scene.roots[0] if self.scene.roots else None)
        self._fill_scene_combo()

    def make_start_scene(self):
        self.project.set_start_scene(self.scene_name)
        self._fill_scene_combo()
        self.log(f"The game now starts in '{self.scene_name}'.", "ok")

    def save_all(self):
        self.save_scene()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeTab):
                w.save()
        self.statusBar().showMessage("Saved", 2000)

    # ====================================================== undo / redo
    def snapshot(self):
        return {"scene": self.scene.to_dict(), "sel": self.selected.id if self.selected else None}

    def checkpoint(self, key=None, force=False):
        now = time.time()
        if key and not force and key == self._last_key and now - self._last_t < 0.9:
            self._last_t = now
            return
        self.undo_stack.append(self.snapshot())
        del self.undo_stack[:-100]
        self.redo_stack.clear()
        self._last_key, self._last_t = (None if force else key), now

    def _restore(self, snap):
        self.scene = Scene.from_dict(snap["scene"])
        self.selected = self.scene.find_id(snap["sel"]) if snap["sel"] else None
        self.rebuild_hierarchy()
        self.inspector.set_object(self.selected)
        self.scene_view.update()
        self.mark_dirty()

    def do_undo(self):
        w = QApplication.focusWidget()
        if isinstance(w, (QPlainTextEdit, QLineEdit)):
            w.undo()
            return
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self._restore(self.undo_stack.pop())
            self._last_key = None

    def do_redo(self):
        w = QApplication.focusWidget()
        if isinstance(w, (QPlainTextEdit, QLineEdit)):
            w.redo()
            return
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self._restore(self.redo_stack.pop())
            self._last_key = None

    # ====================================================== selection / hierarchy
    def rebuild_hierarchy(self):
        self.tree.rebuild(self.scene, self.selected.id if self.selected else None)

    def select(self, obj, from_tree=False):
        self.selected = obj
        if not from_tree:
            self.tree.select_id(obj.id if obj else None)
        self.inspector.set_object(obj)
        self.scene_view.update()
        if obj:
            self.statusBar().showMessage(f"Selected: {obj.name}")

    def touch(self, obj=None, structural=False, light=False):
        self.mark_dirty()
        self.scene_view.update()
        if structural:
            self.rebuild_hierarchy()

    def _on_transform(self):
        self.inspector.sync_transform()

    def _on_transform_done(self):
        self.mark_dirty()

    @property
    def theme_mode(self):
        from .theme import LIGHT
        return "light" if C["bg0"] == LIGHT["bg0"] else "dark"

    def set_theme(self, mode):
        """Dark or light look. Remembered for next time."""
        from PySide6.QtCore import QSettings
        from .theme import build_qss, set_mode
        set_mode(mode)
        QSettings("PawnEngine", "PawnEngine").setValue("theme", self.theme_mode)
        QApplication.instance().setStyleSheet(build_qss())
        self.rebuild_hierarchy()
        self.inspector.set_object(self.selected)
        self.scene_view.update()
        self.statusBar().showMessage(f"{self.theme_mode.title()} theme")

    def check_updates(self, announce=False):
        """Looks for a newer release on a background thread. announce=True also says when you're up to date."""
        import threading
        from PySide6.QtCore import QTimer
        from engine import updates

        box = {}

        def work():
            box["r"] = updates.check()
        t = threading.Thread(target=work, daemon=True)
        t.start()

        def done():
            if t.is_alive():
                QTimer.singleShot(200, done)
                return
            self._show_update(box.get("r", {"status": "offline"}), announce)
        QTimer.singleShot(200, done)

    def _show_update(self, r, announce):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox
        st = r["status"]
        if st == "newer":
            b = QMessageBox(self)
            b.setWindowTitle("Update available")
            b.setText(f"Pawn Engine {r['latest']} is out!")
            b.setInformativeText((r["notes"] + "\n\n" if r["notes"] else "") + "Download the new installer and run it. Your projects stay as they are.")
            go = b.addButton("Download", QMessageBox.AcceptRole)
            b.addButton("Later", QMessageBox.RejectRole)
            b.exec()
            if b.clickedButton() is go:
                QDesktopServices.openUrl(QUrl(r["url"]))
        elif announce:
            msg = {"current": "You have the newest version. 🎉",
                   "unset": "This copy wasn't built by the GitHub installer build, so there is nowhere to check.",
                   "offline": "Couldn't reach the internet to check. Try again later."}[st]
            QMessageBox.information(self, "Updates", msg)

    def _flag_toggled(self, oid, field):
        o = self.scene.find_id(oid)
        if o is None:
            return
        self.checkpoint(force=True)
        setattr(o, field, not getattr(o, field))
        self.mark_dirty()
        self.rebuild_hierarchy()
        self.scene_view.update()
        if o is self.selected:
            self.inspector.set_object(o)

    def _renamed(self, oid, name):
        o = self.scene.find_id(oid)
        name = name.strip()
        if o and name and name != o.name:
            self.checkpoint(force=True)
            o.name = name
            self.mark_dirty()
            self.inspector.set_object(o if o is self.selected else self.selected)

    def sync_from_tree(self):
        cam = self.scene_view.cam_pos()
        byid = {o.id: o for o in self.scene.all()}
        world = {o.id: o.world_pos(cam) for o in self.scene.all()}
        roots = []

        def walk(item, parent):
            o = byid[item.data(0, Qt.UserRole)]
            o.parent = parent
            o.children = []
            (parent.children if parent else roots).append(o)
            for i in range(item.childCount()):
                walk(item.child(i), o)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i), None)
        self.scene.roots = roots
        for o in self.scene.all():
            wx, wy = world[o.id]
            o.set_world_pos(wx, wy, cam)
        self.mark_dirty()
        self.scene_view.update()
        self.inspector.set_object(self.selected)

    def _add_menu(self, button):
        m = QMenu(self)
        for k in BASIC_KINDS:
            m.addAction(icon(k, C["text"], 16), KIND_LABEL[k], lambda k=k: self.add_object(k))
        ui = m.addMenu("UI")
        for k in UI_ADD:
            ui.addAction(icon(k, C["text"], 16), KIND_LABEL[k], lambda k=k: self.add_object(k))
        m.exec(button.mapToGlobal(QPoint(0, button.height())))

    def _tree_menu(self, oid, pos):
        o = self.scene.find_id(oid) if oid else None
        m = QMenu(self)
        sub = m.addMenu("Add child" if o else "Add object")
        for k in ("rect", "circle", "sprite", "text", "empty") + UI_ADD:
            sub.addAction(icon(k, C["text"], 16), KIND_LABEL[k], lambda k=k: self.add_object(k, parent=o))
        parts = m.addMenu("Add part")
        for label in PARTS:
            parts.addAction(label, lambda label=label: self.add_part(label, parent=o))
        helpers = m.addMenu("Add helper")
        for k in HELPER_KINDS:
            helpers.addAction(icon(k, C["text"], 16), KIND_LABEL[k], lambda k=k: self.add_object(k, parent=o))
        if o:
            m.addSeparator()
            m.addAction("Show / hide", lambda: self._flag_toggled(o.id, "active"))
            m.addAction("Unlock" if o.locked else "Lock", lambda: self._flag_toggled(o.id, "locked"))
            m.addAction("Rename   F2", lambda: self.tree.editItem(self.tree._find(o.id), 0))
            m.addAction("Select in scene view", lambda: (self.scene_view.frame(o)))
            m.addSeparator()
            m.addAction("Duplicate", self.duplicate_selected)
            m.addAction("Save as prefab…", lambda: self.save_prefab(o))
            m.addAction("Delete", self.delete_selected)
        m.exec(pos)

    # ====================================================== objects
    def add_part(self, label, parent=None):
        """Add one of the ready-made parts (Part, Ball, Platform, Ramp, Crate)."""
        kind, settings = PARTS[label]
        self.add_object(kind, parent)
        o = self.selected
        if o is None or o.kind != kind:
            return
        o.name = self.scene.unique_name(label)
        for k, v in settings.items():
            setattr(o, k, v)
        self.rebuild_hierarchy()
        self.scene_view.update()
        self.mark_dirty()

    def add_object(self, kind, parent=None):
        if kind == "camera" and self.scene.camera():
            self.statusBar().showMessage("This scene already has a camera.", 4000)
            self.select(self.scene.camera())
            return
        self.checkpoint(force=True)
        o = GameObject(self.scene.unique_name(KIND_LABEL[kind]), kind)
        sv = self.scene_view
        if kind == "rect":
            o.w = o.h = 100
        elif kind == "circle":
            o.w = o.h = 80
            o.color = "#f2b84b"
        elif kind == "sprite":
            o.w = o.h = 100
            imgs = self.project.list_assets("image")
            if imgs:
                o.sprite = imgs[0][0]
        elif kind == "text":
            o.w, o.h, o.text, o.color = 260, 50, "Hello!", "#ffffff"
        elif kind in ("camera", "empty"):
            o.w, o.h = 60, 40
        elif kind in UI_ADD:
            ui_defaults(o)
        elif kind == "polygon":
            o.w = o.h = 120
            o.points = shape_points("hexagon")
            o.color = "#6aa7ff"
        elif kind == "tilemap":
            o.w = o.h = o.tile_size
            o.color = "#6bd38a"
            for c in range(-3, 4):
                o.tiles[f"{c},0"] = 0
            o.solid = True
        elif kind == "particles":
            o.w = o.h = 40
            o.color = "#f2b84b"
        elif kind in ("model", "folder"):
            o.w, o.h = 120, 80
        elif kind == "zone":
            o.w, o.h, o.color, o.trigger = 200, 140, "#4fd1b5", True
        elif kind == "spawn":
            o.w = o.h = 40
        elif kind == "beam":
            o.w, o.h, o.color = 40, 4, "#ff5a5a"
        elif kind == "prompt":
            o.w, o.h, o.text = 120, 120, "Use"
        elif kind == "light":
            o.w = o.h = 300
            o.color = "#ffd27a"
            if self.scene.darkness <= 0:
                self.scene.darkness = 0.6
                self.log("Made the scene dark (0.6) so the light shows. Project > Scene lighting… changes it.", "info")
        self.scene.add(o, parent)
        o.set_world_pos(sv.cx, sv.cy, sv.cam_pos())
        self.select(o)
        self.rebuild_hierarchy()
        self.mark_dirty()
        self.tabs.setCurrentWidget(self.scene_view)

    def delete_selected(self):
        o = self.selected
        if o is None:
            return
        self.checkpoint(force=True)
        self.scene.remove(o)
        self.selected = None
        self.rebuild_hierarchy()
        self.inspector.set_object(None)
        self.scene_view.update()
        self.mark_dirty()

    def duplicate_selected(self):
        o = self.selected
        if o is None:
            return
        self.checkpoint(force=True)
        c = o.clone()
        c.name = self.scene.unique_name(o.name.split(" (")[0])
        self.scene.add(c, o.parent)
        c.x += 24
        c.y += 24
        self.select(c)
        self.rebuild_hierarchy()
        self.mark_dirty()

    # ====================================================== scripts
    def open_script(self, file, line=None):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, CodeTab) and w.file == file:
                self.tabs.setCurrentIndex(i)
                if line:
                    w.show_error(line)
                return w
        try:
            tab = CodeTab(self.project, file)
        except OSError:
            QMessageBox.warning(self, "Script not found", f"I couldn't open {file}.")
            return None
        tab.saved.connect(self.on_script_saved)
        i = self.tabs.addTab(tab, icon("script", C["purple"], 16), file)
        close = QPushButton("✕")
        close.setProperty("flat", True)
        close.setFixedSize(22, 22)
        close.setToolTip("Close this script")
        close.clicked.connect(lambda: self.close_tab(self.tabs.indexOf(tab)))
        self.tabs.tabBar().setTabButton(i, QTabBar.RightSide, close)
        self.tabs.setCurrentIndex(i)
        if line:
            tab.show_error(line)
        tab.edit.setFocus()
        return tab

    def close_tab(self, i):
        if i < 2:
            return
        w = self.tabs.widget(i)
        if isinstance(w, CodeTab):
            w.save()
            self.tabs.removeTab(i)
            w.deleteLater()

    def on_script_saved(self, file):
        if self.selected and any(r["file"] == file for r in self.selected.scripts):
            self.inspector.set_object(self.selected)
        rt = self.game_view.rt
        if rt:
            try:
                n = rt.reload_script(file)
                if n:
                    self.log(f"↻ {file} updated while the game runs", "ok")
                if self.game_view.errored and self._last_error and self._last_error.file == file:
                    self.banner_text.setText(f"{file} was updated. Press Continue to try again.")
            except PawnError as e:
                self.log(e.pretty(), "error")

    def new_script(self, attach_to=None):
        name, ok = QInputDialog.getText(self, "New script", "Name for the script:", text="my_script")
        if not ok or not name.strip():
            return None
        fname = self.project.new_script_name(name)
        self.project.write_script(fname, NEW_SCRIPT)
        self.files.refresh(self.project)
        if attach_to is not None:
            self.attach_script(attach_to, fname)
        self.open_script(fname)
        return fname

    def new_module(self):
        name, ok = QInputDialog.getText(self, "New module script",
                                        "Name for the module (other scripts load it with require):", text="my_module")
        if not ok or not name.strip():
            return None
        fname = self.project.new_module_name(name)
        self.project.write_module(fname, NEW_MODULE.replace("NAME", fname[:-8]))
        self.files.refresh(self.project)
        self.open_script(fname)
        return fname

    def show_add_script_menu(self, obj, button):
        m = QMenu(self)
        m.addAction("＋  New script…", lambda: self.new_script(obj))
        m.addAction("📚  Script gallery…", lambda: self.open_gallery(obj))
        have = {r["file"] for r in obj.scripts}
        existing = [s for s in self.project.list_scripts() if s not in have]
        if existing:
            em = m.addMenu("Your scripts")
            for s in existing:
                em.addAction(s, lambda s=s: self.attach_script(obj, s))
        m.exec(button.mapToGlobal(QPoint(0, button.height())))

    def open_gallery(self, target=None):
        from .gallery import GalleryDialog
        GalleryDialog(self, target if target is not None else self.selected).exec()

    def _attach_preset(self, obj, fname, text):
        if not (self.project.scripts_dir / fname).exists():
            self.project.write_script(fname, text)
            self.files.refresh(self.project)
        self.attach_script(obj, fname)

    def attach_script(self, obj, file):
        self.checkpoint(force=True)
        obj.scripts.append({"file": file, "values": {}})
        self.mark_dirty()
        self.inspector.set_object(obj)

    def _attach_to_selected(self, file):
        if self.selected is None:
            self.statusBar().showMessage("Select an object first, then attach the script.", 4000)
            return
        self.attach_script(self.selected, file)

    def remove_script(self, obj, idx):
        self.checkpoint(force=True)
        del obj.scripts[idx]
        self.mark_dirty()
        self.inspector.set_object(obj)

    def live_value(self, obj, file, name, val):
        rt = self.game_view.rt
        if not rt:
            return
        for inst in rt.instances:
            if inst.obj.id == obj.id and inst.file == file:
                inst.fields[name] = val

    # ====================================================== assets
    def import_assets(self):
        exts = " ".join("*" + e for e in sorted(IMAGE_EXT | SOUND_EXT | FONT_EXT | {".svg"}))
        files, _ = QFileDialog.getOpenFileNames(self, "Import pictures, sounds or fonts", str(Path.home()),
                                                f"Pictures, sounds and fonts ({exts})")
        self.import_paths(files)

    def edit_lighting(self):
        from .dialogs import LightingDialog
        d = LightingDialog(self.scene, self)
        if d.exec():
            self.checkpoint(force=True)
            self.scene.darkness, self.scene.ambient = d.result()
            self.scene_view.update()
            self.mark_dirty()

    def edit_theme(self):
        from .dialogs import ThemeDialog
        d = ThemeDialog(self.project, self)
        if d.exec():
            self.project.set_theme(d.result_theme())
            self.assets.theme = self.project.theme
            self.scene_view.update()
            self.log("UI theme saved", "ok")

    def edit_window(self):
        from .dialogs import WindowDialog
        d = WindowDialog(self.project, self)
        if d.exec():
            self.project.set_window(d.options())
            self.log("Game window saved. It applies to exported games.", "ok")

    def edit_mixer(self):
        from .dialogs import MixerDialog
        d = MixerDialog(self.project, self)
        if d.exec():
            self.project.set_audio_levels(d.levels())
            self.log("Audio levels saved. They apply the next time you press Play.", "ok")

    def import_paths(self, files):
        """Copy pictures and sounds into the project (from the dialog or from drag and drop)."""
        done, skipped = [], []
        svgs = [f for f in files if str(f).lower().endswith(".svg")]
        files = [f for f in files if f not in svgs]
        for f in svgs:
            self.import_svg(f)
        for f in files:
            try:
                rel = self.project.import_asset(f)
            except OSError as e:
                self.log(f"Couldn't import {Path(f).name}: {e}", "error")
                continue
            (done if rel else skipped).append(rel or Path(f).name)
        for rel in done:
            self.log(f"Imported {rel.split('/')[-1]}", "ok")
        if skipped:
            self.log("I can only import pictures (" + ", ".join(sorted(e[1:] for e in IMAGE_EXT)) + ") and sounds ("
                     + ", ".join(sorted(e[1:] for e in SOUND_EXT)) + ") and fonts (ttf, otf). Skipped: " + ", ".join(skipped), "error")
        if done:
            self.files.refresh(self.project)
            # one picture dropped while nothing is selected: make it a picture object right away
            if len(done) == 1 and done[0].split(".")[-1].lower() in {e[1:] for e in IMAGE_EXT} \
                    and self.selected is None:
                self.use_sprite(done[0])

    def import_svg(self, path=None):
        from engine.svg import parse_svg, normalise
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Import SVG", str(Path.home()), "SVG drawings (*.svg)")
            if not path:
                return
        try:
            shapes, notes = parse_svg(Path(path).read_text(encoding="utf-8", errors="replace"))
        except ValueError as e:
            QMessageBox.warning(self, "Import SVG", str(e))
            return
        if not shapes:
            QMessageBox.information(self, "Import SVG", "I couldn't find any shapes in that file.\n"
                                    "Polygons, rectangles, circles, ellipses and paths (with curves) work.")
            return
        self.checkpoint(force=True)
        allp = [pt for sh in shapes for pt in sh["points"]]
        xs, ys = [p[0] for p in allp], [p[1] for p in allp]
        k = 300.0 / max(1e-6, max(max(xs) - min(xs), max(ys) - min(ys)))
        mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        group = GameObject(self.scene.unique_name(Path(path).stem), "empty")
        group.w, group.h = 60, 40
        self.scene.add(group)
        sv = self.scene_view
        group.set_world_pos(sv.cx, sv.cy, sv.cam_pos())
        for i, sh in enumerate(shapes[:300]):
            cx, cy, w, h, pts = normalise([(px - mx, py - my) for px, py in sh["points"]], k)
            o = GameObject(f"Shape {i + 1}", "polygon")
            o.x, o.y, o.w, o.h, o.points, o.color = cx, cy, max(2.0, w), max(2.0, h), pts, sh["color"]
            o.layer = i
            self.scene.add(o, group)
        self.select(group)
        self.rebuild_hierarchy()
        self.mark_dirty()
        self.log(f"Imported {min(len(shapes), 300)} shapes from {Path(path).name}. " + " ".join(notes), "ok" if not notes else "warn")

    def save_prefab(self, o):
        name, ok = QInputDialog.getText(self, "Save as prefab", "Prefab name (scripts use it like  spawn(\"Name\")):",
                                        text=o.name.split(" (")[0])
        name = name.strip() if ok else ""
        if not name:
            return
        try:
            self.project.prefab_path(name)
        except ValueError as e:
            QMessageBox.warning(self, "Save as prefab", str(e))
            return
        if name in self.project.list_prefabs() and QMessageBox.question(
                self, "Replace prefab?", f"A prefab called '{name}' already exists. Replace it?") != QMessageBox.Yes:
            return
        d = o.to_dict()
        d["x"], d["y"] = 0, 0
        d["active"] = True
        self.project.save_prefab(name, d)
        self.files.refresh(self.project)
        self.log(f"Saved prefab '{name}'. Use  spawn(\"{name}\", x, y)  in a script.", "ok")

    def add_prefab(self, name):
        try:
            data = self.project.load_prefab(name)
        except (OSError, ValueError) as e:
            self.log(f"Couldn't read prefab '{name}': {e}", "error")
            return
        self.checkpoint(force=True)
        o = GameObject.from_dict(data)
        for n in o.iter_tree():
            n.id = uuid.uuid4().hex[:8]
        o.name = self.scene.unique_name(o.name)
        self.scene.add(o)
        sv = self.scene_view
        o.set_world_pos(sv.cx, sv.cy, sv.cam_pos())
        self.select(o)
        self.rebuild_hierarchy()
        self.mark_dirty()
        self.tabs.setCurrentWidget(self.scene_view)

    def delete_file(self, rel):
        path = self.project.path / rel if not rel.startswith("scripts/") else self.project.path / rel
        if QMessageBox.question(self, "Delete file", f"Delete {path.name}? This can't be undone.") != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except OSError as e:
            QMessageBox.warning(self, "Couldn't delete", str(e))
            return
        self.files.refresh(self.project)

    def use_sprite(self, rel):
        o = self.selected
        pm = QPixmap(str(self.project.path / rel))
        if o is None or o.kind in ("camera", "empty", "text"):
            self.add_object("sprite")
            o = self.selected
        self.checkpoint(force=True)
        if o.kind != "sprite" or not o.sprite:
            if not pm.isNull():
                k = 160.0 / max(pm.width(), pm.height())
                o.w, o.h = pm.width() * k, pm.height() * k
        o.kind = "sprite"
        o.sprite = rel
        self.rebuild_hierarchy()
        self.inspector.set_object(o)
        self.scene_view.update()
        self.mark_dirty()

    # ====================================================== play
    def play(self):
        if self.game_view.running:
            self.stop()
            return
        self.save_all()
        self.hide_banner()
        try:
            self.game_view.start(self.scene.to_dict(), self.scene_name)
        except PawnError as e:
            self.log(e.pretty(), "error")
            self._last_error = e
            self.show_banner(e, "Couldn't start your game: ")
            if e.file:
                self.open_script(e.file, e.line)
            return
        self.tabs.setCurrentWidget(self.game_view)
        self.game_view.setFocus()
        self.log("▶ Game started", "info")

    def stop(self):
        self.game_view.stop()
        self.hide_banner()
        self.tabs.setCurrentWidget(self.scene_view)
        self.log("■ Game stopped", "info")

    def on_game_state(self):
        gv = self.game_view
        running = gv.running
        self.btn_play.setText("  Stop" if running else "  Play")
        self.btn_play.setIcon(icon("stop" if running else "play", "#ffffff", 16))
        self.btn_play.setProperty("running", running)
        self.btn_play.style().unpolish(self.btn_play)
        self.btn_play.style().polish(self.btn_play)
        self.btn_pause.setEnabled(running)
        self.btn_step.setEnabled(running and gv.paused)

    def on_game_error(self, err):
        self._last_error = err
        self.log(err.pretty(), "error")
        self.show_banner(err, "Your game paused: ")
        if err.file:
            self.open_script(err.file, err.line)
            self.tabs.setCurrentWidget(self.game_view if False else self.tabs.currentWidget())

    def show_banner(self, err, prefix):
        self.banner_text.setText(prefix + err.pretty())
        self.banner_show.setVisible(bool(err.file and err.line))
        self.banner_go.setVisible(self.game_view.running)
        self.banner.show()

    def hide_banner(self):
        self.banner.hide()
        self._last_error = None

    def _continue(self):
        self.hide_banner()
        self.game_view.resume_after_error()
        self.tabs.setCurrentWidget(self.game_view)
        self.game_view.setFocus()

    def _show_error_line(self):
        e = self._last_error
        if e and e.file:
            self.open_script(e.file, e.line)

    # ====================================================== misc
    def export(self):
        self.save_all()
        name, ok = QInputDialog.getText(self, "Export game", "Name of your game:", text=self.project.name)
        if not ok or not name.strip():
            return
        dest = QFileDialog.getExistingDirectory(self, "Where should the game folder go?", str(Path.home() / "Desktop")
                                                if (Path.home() / "Desktop").exists() else str(Path.home()))
        if not dest:
            return
        try:
            try:
                folder, launcher, real_exe = export_game(self.project, dest, name.strip())
            except FileExistsError:
                if QMessageBox.question(self, "Replace existing folder?",
                                        "A folder with that name is already there. Replace it with the new export?\n\n"
                                        "Everything inside that folder will be deleted.") != QMessageBox.Yes:
                    return
                folder, launcher, real_exe = export_game(self.project, dest, name.strip(), overwrite=True)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        box = QMessageBox(self)
        box.setWindowTitle("Game exported")
        if real_exe:
            box.setText(f"Your game is ready!\n\nOpen the folder and double-click  {launcher.name}.\n"
                        f"You can zip the whole folder and send it to friends.")
        else:
            box.setText("Game folder created.\n\nYou are running Pawn Engine from source, so this folder needs Python "
                        f"to play (double-click “{launcher.name}”).\n\nTo get a real .exe, build Pawn Engine with "
                        "build_exe.bat, then export again from that app.")
        open_btn = box.addButton("Open folder", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def show_guide(self):
        d = QDialog(self)
        d.setWindowTitle("Pawn quick guide")
        d.resize(760, 640)
        v = QVBoxLayout(d)
        t = QPlainTextEdit(GUIDE)
        t.setReadOnly(True)
        t.setFont(mono_font(10))
        v.addWidget(t)
        b = QPushButton("Got it")
        b.setProperty("primary", True)
        b.clicked.connect(d.accept)
        v.addWidget(b, alignment=Qt.AlignRight)
        d.exec()

    def about(self):
        QMessageBox.about(self, "About Pawn Engine",
                          "<b>Pawn Engine</b><br>A tiny, friendly language and 2D game editor.<br><br>"
                          "Start small like a pawn — promote to a queen.")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.import_paths(paths)
            e.acceptProposedAction()

    def close_to_menu(self):
        self._to_menu = True
        self.close()

    def closeEvent(self, e):
        try:
            self.game_view.stop()
            self.save_all()
        except Exception:
            pass
        e.accept()
        if self._to_menu:
            self.back_to_menu.emit()
