# ♟ Pawn Engine

Make 2D games with **Pawn**, a tiny indentation-based language. No `{}` scary braces.

## Install (easiest)

Download **PawnEngine-Setup.exe** from the website or the Releases page and run it. To publish your own installer and
download page, follow **GITHUB_GUIDE.md**.

## Run it from the source (Windows)

1. Install Python 3.10+ from python.org (tick **Add python.exe to PATH**).
2. Double-click **`run.bat`**.

## Make the .exe

Double-click **`build_exe.bat`**. When it finishes you get `dist\PawnEngine\PawnEngine.exe`
(with the pawn icon). Keep the whole `PawnEngine` folder together; zip it to share.

To export a *game* as its own .exe: open a project, then **File > Export game**.
This only makes a real `.exe` when you run the app you built with `build_exe.bat`. If you run Pawn Engine from
source (`run.bat`), the exported folder needs Python and the packages in `requirements.txt` to play.
If a folder with the game's name already exists you are asked before it is replaced.

## Faster (optional)

Double-click **`build_native.bat`** once to build the Rust core (it installs Rust if needed). Everything still works without it.
The game view draws with OpenGL when it can.

## How it works

- **Main menu**: create a project (Coin collector or Blank) or reopen a recent one.
- **Scene view**: drag the arrows to move things, drag corners to resize, right-drag to pan, scroll to zoom, `F` to focus.
- **Hierarchy**: an Explorer-style tree. Drag an object onto another to group it, click the eye to hide and the lock to stop picking, type to search.
- **Project panel**: your scripts, **module scripts**, pictures and sounds. Drag pictures (`png jpg gif webp bmp`)
  and sounds (`wav ogg mp3`) into it, or onto the window, to import them.
- **Properties**: fold cards, search properties; edit position, color, layer, opacity, tags, physics, and attach scripts. Variables at the top of a script appear here as fields.
- **Play** runs the game. Saving a script hot-reloads it while playing.
- Everything autosaves. Ctrl+Z / Ctrl+Y undo and redo.

## Pawn in 30 seconds

```
speed = 260
jump = 640

on start
    game.score = 0

when key("left") or key("a")
    self.x -= speed * dt

when pressed("space")
    self.vy = -jump
```

## What's new in 0.5

```
speed = 260        # range 0 600       <- becomes a slider in the Inspector
mode = "easy"      # choice easy, hard

on start
    darkness(0.7)                     # a dark scene; Light objects cut through it
    breakpoint("check my values")     # pause and look at the Watch panel
```

Autocomplete and typo hints, Inspector sliders from comments, a Watch panel with live editing, a script gallery with 40+
scripts, a "Menu and level" template, lights and darkness, parallax, and SVG curves.

## What's new in 0.4

```
on touch as who                      # on a coin (tick Trigger in the Inspector)
    if who.has_tag("player")
        game.coins += 1
        shake(4, 0.15)
        self.destroy()

on click                             # on a "Play" button
    load_scene("Level 1")

on start
    if load_game("slot1")
        print("welcome back, score", game.score)
    enemy = spawn("Slime", 300, 100)  # spawn from a prefab file
```

Several scenes, saving, prefabs, one-way platforms, ramps, triggers, collision groups, tile maps, particles, screen shake,
polygons and SVG import.

## What's new in 0.3

```
on start
    self.play_anim("run")            # sprite-sheet animation set up in the Inspector
    play_music("theme", true, 0.7)
    volume("music", 0.5)

on click                              # on a Button object
    play("coin")
    game.score += 1

on change as v                        # on a Slider object
    volume("music", v)
```

Sprite sheets and animations, custom fonts, `vx` with friction and bounce, an audio mixer, and UI objects (button,
progress bar, slider, checkbox, text box) with anchors, a project theme and `on click` style events.

## What's new in 0.2

```
local hits = 0                       # private variable; written at the top it is remembered between frames
state = {hp = 3, name = "orc"}       # tables: state.hp += 1   each k, v in pairs(state)

on start
    wait 2 seconds                   # pauses this block only; the game keeps running
    tween self.x to 300 over 1 second ease out
    tools = require("tools")         # load a module script

watch game.score as s                # runs whenever the value changes
    print("score is {s}")

state idle                           # little state machines
    when key("space")
        go jump
state jump
    on enter
        self.jump(600)
    when self.on_ground
        go idle
```

- **Module scripts** (`＋ New module`) hold shared code. They run once, must end with `return`, and every script that
  calls `require("name")` gets the same table. Saving a module updates running games.
- **`game.pawn`**: a script with this name runs once for the whole game, not for one object.
- **Signals**: `s = signal()`, `s.connect(fn)`, `s.fire(x)`, `s.once(fn)`, `s.wait()`; `event("name")` is a signal
  shared by name between all scripts.
- **Tags**: `self.tag("enemy")`, `all("#enemy")`, `tagged("enemy")`, `touching("#enemy")`.
- **Pictures and layers**: `self.sprite`, `self.flip_x`, `self.alpha`, `self.layer`. Higher layers draw on top.
- **Sound**: `play("coin")`, `play_music("theme")`, `stop_music()`, `volume("music", 0.5)`.
- A `when` block that is still waiting does not start a second copy of itself. A `when`/`every`
  block's plain variables (like `n = 0`) are temporary; Pawn tells you once and suggests `local` or a top-level variable.
- Interpolation inside text can't contain double quotes: write `"{find('Coin').x}"`.
- Tweens are started with `tween ...` and keep running by themselves; use `wait tweens` to pause until they finish.

Run the tests with `python -m unittest discover -s tests` (the editor smoke test is skipped if PySide6 is missing).

Mistakes show a friendly message with a "Did you mean...?" hint, and the game pauses so you can fix the script and press Continue.

## About the name

The **Pawn** language in this engine (indentation-based, Lua-flavored, made for 2D games) has nothing to do with
CompuPhase's "Pawn" embedded scripting language (C-like, used for game servers and devices). The names overlap and
CompuPhase's language has been around since 1998. Pawn Engine is not affiliated with it, and
`.pawn`/`.pawnmod`/`.pawnproj` here are this engine's own formats. If you plan to sell or widely publish the engine,
consider a distinct name to avoid confusion.
