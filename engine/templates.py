"""Project templates: ready-made scenes to start from."""
from .gameobject import GameObject
from .presets import PRESETS
from .scene import Scene
from .sounds import make_default_sounds

GAME_SCRIPT_TEXT = '''# This script runs once for the whole game, not for one object.
# (A script called game.pawn in the scripts folder is always treated this way.)

on start
    game.score = 0
'''

UTILS_MODULE_TEXT = '''# An example module script. Use it from any script:
#     utils = require("utils")
#     self.x = utils.wrap(self.x, -400, 400)

def wrap(v, lo, hi)
    span = hi - lo
    return lo + (v - lo) % span

def approach(v, target, step)
    if v < target
        return min(v + step, target)
    return max(v - step, target)

return {wrap = wrap, approach = approach}
'''


def _obj(scene, name, kind, x, y, w, h, color, **kw):
    o = GameObject(name, kind, x=x, y=y, w=w, h=h, color=color, **kw)
    scene.add(o)
    return o


def _gallery_script(proj, label):
    fname, text = PRESETS[label]
    proj.write_script(fname, text)
    return fname


def build_menu_game(proj):
    """Two scenes: a title screen with a Play button and volume slider, and a small level with a goal back to the menu."""
    make_default_sounds(proj)
    for label in ("Platformer movement", "Collectible", "Score display", "Respawn at checkpoint"):
        _gallery_script(proj, label)
    play_f = _gallery_script(proj, "Play button")
    vol_f = _gallery_script(proj, "Volume slider")
    goal_f = _gallery_script(proj, "Goal (next scene)")
    proj.write_script("game.pawn", GAME_SCRIPT_TEXT)

    level = Scene()
    _obj(level, "Main Camera", "camera", 0, 0, 60, 40, "#f2b84b").follow = "Player"
    tiles = {f"{c},0": 0 for c in range(-12, 28)}
    tiles.update({f"{c},-3": 1 for c in range(4, 8)})
    tiles.update({f"{c},-5": 1 for c in range(12, 15)})
    _obj(level, "Ground Tiles", "tilemap", -400, 280, 32, 32, "#3a4256", solid=True, tiles=tiles, tile_size=32)
    player = _obj(level, "Player", "rect", -360, 200, 40, 56, "#f2b84b", body=True, tags=["player"])
    player.scripts = [{"file": "platformer_move.pawn", "values": {}}, {"file": "respawn.pawn", "values": {}}]
    for i, (cx, cy) in enumerate([(-100, 240), (0, 160), (120, 100), (240, 240), (330, 60)]):
        c = _obj(level, "Coin" if i == 0 else f"Coin ({i})", "circle", cx, cy, 28, 28, "#ffd35c", trigger=True)
        c.scripts = [{"file": "collectible.pawn", "values": {}}]
    goal = _obj(level, "Goal", "rect", 640, 232, 40, 64, "#6bd38a", trigger=True)
    goal.scripts = [{"file": goal_f, "values": {"next_scene": "Main"}}]
    score = _obj(level, "Score Text", "text", -310, -230, 300, 40, "#ffffff", text="Score: 0", text_size=28, align="left",
                 hud=True)
    score.scripts = [{"file": "score_text.pawn", "values": {}}]
    _obj(level, "Help Text", "text", 0, 240, 760, 30, "#8a91a3", text="Arrow keys to move  •  Space to jump  •  Reach the green door",
         text_size=20, hud=True)
    proj.save_scene(level.to_dict(), "Level 1")

    menu = Scene()
    _obj(menu, "Main Camera", "camera", 0, 0, 60, 40, "#f2b84b")
    _obj(menu, "Title", "text", 0, -120, 700, 80, "#f2b84b", text=proj.meta.get("name", "My Game"), text_size=64)
    btn = _obj(menu, "Play Button", "button", 0, 0, 220, 60, "", text="Play", text_size=26, hud=True, anchor="center")
    btn.scripts = [{"file": play_f, "values": {}}]
    _obj(menu, "Volume Label", "text", 0, 90, 300, 30, "#8a91a3", text="Music volume", text_size=18, hud=True)
    sl = _obj(menu, "Volume Slider", "slider", 0, 125, 260, 24, "", value=1.0, hud=True, anchor="center")
    sl.scripts = [{"file": vol_f, "values": {}}]
    return menu


def build_template(kind, proj):
    scene = Scene()
    cam = _obj(scene, "Main Camera", "camera", 0, 0, 60, 40, "#f2b84b")
    if kind == "blank":
        return scene
    if kind == "menu":
        return build_menu_game(proj)
    make_default_sounds(proj)
    for label in ("Platformer movement", "Collectible", "Score display"):
        fname, text = PRESETS[label]
        proj.write_script(fname, text)
    proj.write_script("game.pawn", GAME_SCRIPT_TEXT)
    proj.write_module("utils.pawnmod", UTILS_MODULE_TEXT)
    cam.x, cam.y, cam.follow = -300, 100, "Player"
    ground = _obj(scene, "Ground", "rect", 300, 300, 1800, 60, "#3a4256", solid=True)
    ground.name = "Ground"
    for i, (px, py, pw) in enumerate([(60, 190, 180), (340, 110, 180), (620, 190, 180)]):
        _obj(scene, "Platform" if i == 0 else f"Platform ({i})", "rect", px, py, pw, 24, "#4a5570", solid=True)
    player = _obj(scene, "Player", "rect", -300, 238, 40, 56, "#f2b84b", body=True)
    player.scripts = [{"file": "platformer_move.pawn", "values": {}}]
    coins = [(-150, 235), (200, 235), (480, 235), (60, 150), (340, 70), (620, 150)]
    for i, (cx, cy) in enumerate(coins):
        c = _obj(scene, "Coin" if i == 0 else f"Coin ({i})", "circle", cx, cy, 28, 28, "#ffd35c")
        c.scripts = [{"file": "collectible.pawn", "values": {}}]
    score = _obj(scene, "Score Text", "text", -310, -230, 300, 40, "#ffffff", text="Score: 0",
                 text_size=28, align="left", hud=True)
    score.scripts = [{"file": "score_text.pawn", "values": {}}]
    _obj(scene, "Help Text", "text", 0, 240, 700, 30, "#8a91a3", text="Arrow keys or A / D to move  •  Space to jump",
         text_size=20, hud=True)
    return scene


TEMPLATES = {
    "coin": ("Coin collector", "A small playable game: run, jump and grab coins. Great for learning."),
    "menu": ("Menu and level", "Two scenes: a title screen with a Play button, a volume slider, a tile-map level and a goal."),
    "blank": ("Blank", "Just a camera. Start from nothing."),
}
