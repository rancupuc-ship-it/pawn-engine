# Changelog

## 1.2 "Installer"

- **Real installer**: `PawnEngine-Setup.exe` (Inno Setup) with a wizard, Start Menu and Desktop shortcuts, Uninstall, and
  double-click to open `project.pawnproj` files. Installs for just you, no admin needed.
- **GitHub builds it for you**: push a version tag and the workflow builds the Rust core, the app, the installer and a
  portable zip, then attaches them to the release. See `GITHUB_GUIDE.md`.
- **Download website** in `site/` (published with GitHub Pages) with a Download button that always points to the latest release.
- **Check for updates** (Help menu) plus a quiet check once a day; it only speaks up when a newer version exists.
- `python main.py PROJECT` opens a project directly.

## 1.1 "Easier + More"

**Speed**
- **GPU world drawing**: instanced quads, a texture atlas, static tile maps, culling, a lighting/darkness shader, particles and
  ropes all drawn by OpenGL. Falls back to the old painter if OpenGL isn't available.
- **Rust core** (`native/`): physics, particle packing and A* pathfinding. `build_native.bat` installs Rust if it's missing and
  builds it; if the core isn't there, the Python versions run (same results, slower).
- **Faster Pawn**: scripts that can't `wait` run inline, quicker math/compare/name lookups. `python tools/bench.py` shows timings.

**Easier code**
- `a ?? b` (use b when a is none), `+=` style operators everywhere, `can_use(name, seconds)` / `wait_left(name)` cooldowns,
  `shuffle`, `wrap`, `approach`, `smoothstep`, `map_range`, `snap`, `chance`, `atan2`, `radians`, `degrees`, `tan`, `angle_to`.
- Friendlier errors with hints.

**More engine**
- Particles 2.0: color/alpha/size over life, spin, drag, wind, shapes, bursts, presets.
- `find_path` (A*), `raycast`, `raycast_dir`, `can_see`; `rope`, `spring`, `weld`; `effect("shake" | "blur" | ...)`; gamepad (`pad`,
  `pad_pressed`, `pad_axis`, `pad_rumble`, ...; XInput on Windows).
- **Roblox-style objects**: Model, Folder, Zone, Spawn point (`respawn(self)`, `spawn_point()`), Beam, Prompt (`on prompt`, E key),
  plus ready-made Parts (Part, Ball, Platform, Ramp, Crate) under Object > Add.

**Editor**
- New Explorer-style Hierarchy: SVG icon per object type, eye (hide) and lock buttons, search, remembers folded groups.
- Properties panel with folding cards and property search; cards no longer squash in short windows.
- Dark and light themes (View menu, `Ctrl+Shift+T`), rounder and roomier look.

## 1.0 "Ready"

- **Game window** (Project > Game window): title, size, resizable, start in fullscreen. Put `icon.png` in your
  project's `assets` folder for your own window icon. Exported games use all of it.
- **Slimmer exe**: `build_exe.bat` leaves out Qt parts the engine never uses (web, QML, charts, SQL, test tools) and
  Pillow, so `PawnEngine.exe` and every exported game are smaller.
- **Name**: Pawn Engine's language is unrelated to CompuPhase's "Pawn" embedded language (see the README note).

## 0.5 "Polish"

**SVG**
- Import now reads curves (cubic and quadratic Bezier, smooth versions, arcs) plus circles and ellipses. They are
  flattened into polygons.

**Writing code**
- Autocomplete (keywords, built-ins, your own names; after `self.` / `camera.` / `mouse.` the right members).
- Linter: unknown names and `self.` typos with "Did you mean...", plus tips for values that are never used.
- Click a word to see its signature and description in the status line.
- `speed = 260  # range 0 600` makes Inspector sliders; `# choice a, b` drop-downs; `# color` color buttons.

**Debugging**
- `breakpoint()` pauses the game; the new Watch panel shows `game` and the selected object's variables and lets you
  change them while playing.

**Content**
- Script gallery with 40+ ready-made scripts in 6 groups, and a "Menu and level" project template.
- `text.slice(a, b)`.

**Look**
- Lights and scene darkness (`darkness()`, `ambient()`, Add > Light), parallax per object.

## 0.4 "Real games"

**Scenes and saving**
- Many scenes per project: Scene box in the toolbar, New / Delete / "Make first scene" in the Project menu.
- `load_scene("name")`, `scene_name()`. `game` data and `game.pawn` carry over; the old scene's scripts stop.
- `save_game`, `load_game`, `has_save`, `delete_save`, `saves` (JSON files in the project's `saves/` folder).

**Prefabs**
- Right-click an object > Save as prefab. `spawn("Name", x, y)` uses scene objects first, then prefabs.

**Physics**
- One-way platforms, ramps (rising left or right), triggers, 8 collision groups with a mask.
- `on touch as who` / `on untouch as who` events (fast, uses a grid, so hundreds of pickups are fine).

**Drawing**
- Tile maps (paint in the Scene, solid tiles, script API), particle emitters, screen shake, polygons and SVG import.

## 0.3 "Pictures, Sound & Menus"

**Pictures**
- Sprite sheets: cut a picture into Columns x Rows and show any frame (`self.frame`).
- Named animations (`run = 0-3 @ 10 loop`), `play_anim`, `stop_anim`, `anim`, `playing`, autoplay choice.
- Custom fonts (`.ttf`, `.otf`) for text and UI, imported like pictures and sounds.

**Physics**
- `vx` (sideways speed), ground Friction, Bounce, and `push(dx, dy)`.

**Sound**
- Audio mixer: master / music / sound volumes, `volume()`, `get_volume()`, `fade_music()`, `pause_music()`,
  `resume_music()`, `mute()`, `music_playing()`, `play(name, volume)`. Starting volumes in Project > Audio mixer.

**UI**
- New objects: Button, Progress bar, Slider, Checkbox, Text box (Object > Add > UI).
- Anchors keep them on a screen edge or corner, also with zoom.
- Script events: `on click`, `press`, `release`, `hover`, `leave`, `change [as v]`, `submit [as text]`.
- Project-wide UI theme (colors, roundness, font); any object can override its own colors.
- `mouse.clicked`, `typing()`, `over_ui()`.

## 0.2 "Solid & Alive"

**Fixes**
- Exporting a game named `..` could delete the folder above the one you picked. Names are now sanitised, and an
  existing folder is only replaced after you confirm.
- Values set in the Inspector now reach top-level values that are worked out from them
  (`double = speed * 2`).
- `self.size` really exists now (the font size of a Text object).
- Builtins give friendly messages instead of leaking Python errors (`abs("a")`, `sqrt(-1)`, ...).
- `touching()`, `find()`, `all()` and `nearest()` no longer slow down with hundreds of objects
  (400 coins: 126 ms -> 2 ms per frame).
- Scripts get a time budget (100 ms per block, 300 ms per frame) instead of a step count.
- `"x" * n` is capped at a million letters.
- Falling is sub-stepped, so laggy frames can't push an object through a floor.
- Hot reload keeps the running values of variables whose default didn't change.
- `recent.json` with bad content no longer crashes the menu; script and scene saves are atomic.
- Scripts are only re-read from disk when they change (spawning is cheaper).

**Language**
- `local`, tables (`{a = 1}`), `pairs/keys/values/range/sorted/sum/type`, more list and text methods, `^` and `//`.
- `each k, v in ...`, `seed()` for repeatable random numbers.
- `wait N seconds`, `wait until ...`, `wait frame`, `wait tweens` (runs on greenlets, works at any depth).
- `signal()`, `event("name")`, `watch`, `state` / `go`, tags (`#tag`), `tween`.
- Module scripts (`.pawnmod`) with `require("name")`, and a global `game.pawn`.
- A one-time tip when a `when` / `every` block makes a plain temporary variable.

**Engine and editor**
- Code split into smaller files (`pawnlang/`: errors, values, context, program, members, coroutines; `engine/`:
  gameobject, proxies, physics, signals, tween, builtins, modules, script_instance, presets, templates, sounds, recent).
- Layers (draw order), opacity and flip for objects; tags in the Inspector.
- Drag-and-drop import of pictures and sounds (`png jpg gif webp bmp wav ogg mp3`).
- `play_music`, `stop_music`, `volume`.
- Scene and project files carry `"format": 1`.
- New dependency: `greenlet`.
- Test suite in `tests/`.
