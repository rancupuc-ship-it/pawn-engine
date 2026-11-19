"""Starter scripts offered in the editor."""

PRESETS = {
    "Platformer movement": ("platformer_move.pawn", '''# Platformer movement: arrow keys or A / D to move, Space to jump.
# Tip: tick "Affected by gravity" on this object in the Inspector.

speed = 260
jump_power = 640
fall_limit = 900

local home_x = 0
local home_y = 0

on start
    home_x = self.x
    home_y = self.y

when key("left") or key("a")
    self.x = self.x - speed * dt

when key("right") or key("d")
    self.x = self.x + speed * dt

when pressed("space") or pressed("up") or pressed("w")
    if self.on_ground
        play("jump")
    self.jump(jump_power)

when self.y > fall_limit
    self.x = home_x
    self.y = home_y
    self.vy = 0
'''),
    "Top-down movement": ("topdown_move.pawn", '''# Top-down movement: arrow keys or W A S D.

speed = 220

when true
    if key("left") or key("a")
        self.x = self.x - speed * dt
    if key("right") or key("d")
        self.x = self.x + speed * dt
    if key("up") or key("w")
        self.y = self.y - speed * dt
    if key("down") or key("s")
        self.y = self.y + speed * dt
'''),
    "Collectible": ("collectible.pawn", '''# Collectible: disappears when the Player touches it and adds 1 to the score.
# The object that collects it must be named "Player".

when touching("Player")
    game.score = game.score + 1
    play("coin")
    self.destroy()
'''),
    "Score display": ("score_text.pawn", '''# Shows the score. Attach this to a Text object.

when true
    self.text = "Score: {game.score}"
'''),
    "Blink (uses wait)": ("blink.pawn", '''# Blinks forever. 'wait' pauses this block without freezing the game.

on_time = 0.6
off_time = 0.3

on start
    while true
        self.alpha = 0.2
        wait off_time seconds
        self.alpha = 1
        wait on_time seconds
'''),
    "Spawner (uses wait)": ("spawner.pawn", '''# Spawns copies of an object. Make an object called "Coin", untick Active so it is a template.

what = "Coin"
how_many = 5
gap = 1.0

on start
    repeat how_many times
        spawn(what, random(-300, 300), -150)
        wait gap seconds
    print("done spawning")
'''),
    "Patrol (uses states)": ("patrol.pawn", '''# Walks right, then left, forever, using a state machine.

speed = 120
time_each_way = 2

state right
    on enter
        self.flip_x = false
    every 0.016 seconds
        self.x += speed * 0.016
    after time_each_way seconds
        go left

state left
    on enter
        self.flip_x = true
    every 0.016 seconds
        self.x -= speed * 0.016
    after time_each_way seconds
        go right
'''),
    "Spin": ("spin.pawn", '''# Spins the object around.

speed = 90

when true
    self.angle = self.angle + speed * dt
'''),
}

NEW_SCRIPT = '''# Scripts belong to the object they are attached to. Use "self" to talk to it.
# Variables at the top (like speed) show up in the Inspector so you can tweak them.

speed = 200

on start
    print("Hello from {self.name}!")

when key("right")
    self.x = self.x + speed * dt
'''

NEW_MODULE = '''# A module script holds code and values that other scripts share.
# It runs once, the first time someone asks for it, and must end with a return.
# Use it from a script like this:   tools = require("NAME")

def double(n)
    return n * 2

return {double = double, gravity = 900}
'''


def _extend_with_gallery():
    from .gallery import GALLERY
    for _cat, label, fname, _desc, source in GALLERY:
        PRESETS[label] = (fname, source)


_extend_with_gallery()
