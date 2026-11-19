"""The script gallery: ready-made behaviors, grouped. Each one is a normal script the user can read and change."""

# (category, label, file, one-line description, source)
GALLERY = [
("Movement", "Double jump", "double_jump.pawn", "Jump twice before landing. Needs 'Affected by gravity'.", '''# Double jump: press Space, press it again in the air.
# Tick "Affected by gravity" on this object.

jump_power = 620    # range 200 1200
max_jumps = 2       # range 1 5

local jumps_left = 2

when self.on_ground
    jumps_left = max_jumps

when pressed("space") and jumps_left > 0
    self.jump(jump_power)
    jumps_left -= 1
'''),
("Movement", "Dash", "dash.pawn", "Press Shift to dash in the direction you face.", '''# Dash: press Shift for a quick burst of speed.

power = 700         # range 200 1500
cooldown = 0.6      # range 0.1 3

local ready = true

when pressed("shift") and ready
    ready = false
    dir = 1
    if self.flip_x
        dir = -1
    if key("left")
        dir = -1
    if key("right")
        dir = 1
    self.vx = dir * power
    wait cooldown seconds
    ready = true
'''),
("Movement", "Slippery movement (ice)", "ice_move.pawn", "Accelerate and slide using vx and friction.", '''# Slippery movement. Set Friction on this object in the Inspector (try 2).
# Tick "Affected by gravity" so it stands on the floor.

push_power = 900    # range 200 2000
top_speed = 320     # range 100 800

when key("left")
    self.vx = max(self.vx - push_power * dt, -top_speed)

when key("right")
    self.vx = min(self.vx + push_power * dt, top_speed)
'''),
("Movement", "Follow the mouse", "follow_mouse.pawn", "Glides toward the mouse pointer.", '''# Follows the mouse pointer smoothly.

smoothness = 6      # range 1 20

when true
    self.x = lerp(self.x, mouse.x, min(1, smoothness * dt))
    self.y = lerp(self.y, mouse.y, min(1, smoothness * dt))
'''),
("Movement", "Drag with the mouse", "drag.pawn", "Pick the object up with the mouse and move it.", '''# Click and hold to drag this object around.

local held = false
local grab_x = 0
local grab_y = 0

when mouse.clicked and abs(mouse.x - self.x) < self.width / 2 and abs(mouse.y - self.y) < self.height / 2
    held = true
    grab_x = self.x - mouse.x
    grab_y = self.y - mouse.y

when held and mouse.down
    self.x = mouse.x + grab_x
    self.y = mouse.y + grab_y

when held and not mouse.down
    held = false
'''),
("Movement", "Chase the player", "chase.pawn", "Walks toward an object tagged 'player'.", '''# Chases the first object tagged "player" (add the tag in the Inspector).

speed = 110         # range 20 400
sight = 400         # range 50 1200

when true
    target = find("#player")
    if target != none and distance(self, target) < sight
        if target.x > self.x
            self.x += speed * dt
        else
            self.x -= speed * dt
'''),
("Movement", "Move back and forth", "ping_pong.pawn", "Moves left and right between two points (a moving platform).", '''# Slides back and forth. Great for moving platforms (tick Solid).

distance_each_way = 160    # range 20 600
speed = 90                 # range 10 400

local start_x = 0
local dir = 1

on start
    start_x = self.x

when true
    self.x += dir * speed * dt
    if self.x > start_x + distance_each_way
        dir = -1
    if self.x < start_x - distance_each_way
        dir = 1
'''),
("Movement", "Bounce around", "bounce_around.pawn", "Flies in a straight line and bounces off the edges of the view.", '''# A ball that bounces around the screen.

vx_start = 200
vy_start = 150

local dx = 0
local dy = 0

on start
    dx = vx_start
    dy = vy_start

when true
    self.x += dx * dt
    self.y += dy * dt
    if self.x < -480 or self.x > 480
        dx = -dx
    if self.y < -270 or self.y > 270
        dy = -dy
'''),
("Movement", "Orbit", "orbit.pawn", "Circles around the point where it started.", '''# Circles around its starting point.

radius = 120       # range 10 500
speed = 90         # range 10 360

local cx = 0
local cy = 0
local a = 0

on start
    cx = self.x
    cy = self.y

when true
    a += speed * dt
    self.x = cx + cos(a) * radius
    self.y = cy + sin(a) * radius
'''),
("Movement", "Random wander", "wander.pawn", "Picks a spot nearby, walks there, rests, repeats.", '''# Wanders around randomly.

range_x = 150      # range 20 600
speed = 80         # range 10 300

local home_x = 0

on start
    home_x = self.x
    while true
        goal = home_x + random(-range_x, range_x)
        while abs(goal - self.x) > 4
            if goal > self.x
                self.x += speed * dt
            else
                self.x -= speed * dt
            wait frame
        wait random(0.5, 2) seconds
'''),
("Movement", "Jump pad", "jump_pad.pawn", "Launches anything that lands on it. Tick Trigger.", '''# Jump pad: tick "Trigger" on this object. Whatever touches it is launched upward.

power = 900        # range 200 1800

on touch as who
    who.jump(power)
    play("jump")
'''),
("Collecting", "Health pickup", "health_pickup.pawn", "Adds health to game.hp when the player touches it.", '''# Health pickup: tag the player "player". Tick Trigger on this object.

amount = 1         # range 1 10
max_hp = 5

on touch as who
    if who.has_tag("player")
        game.hp = min(max_hp, game.hp + amount)
        play("coin")
        self.destroy()
'''),
("Collecting", "Key and door", "key.pawn", "A key you pick up; the door opens with game.has_key.", '''# Key: tag the player "player", tick Trigger on the key.
# On the door object use the 'Door' script from the gallery.

on touch as who
    if who.has_tag("player")
        game.has_key = true
        play("coin")
        self.destroy()
'''),
("Collecting", "Door (needs a key)", "door.pawn", "Disappears when the player touches it carrying the key.", '''# Door: opens if game.has_key is true. Tick Trigger on the door.

on touch as who
    if who.has_tag("player") and game.has_key
        game.has_key = false
        play("coin")
        self.destroy()
'''),
("Collecting", "Checkpoint", "checkpoint.pawn", "Remembers where the player should respawn.", '''# Checkpoint: touch it and respawn here later (game.check_x / game.check_y).
# Tick Trigger. The player needs the tag "player".

on touch as who
    if who.has_tag("player")
        game.check_x = self.x
        game.check_y = self.y - 20
        self.alpha = 1
        play("coin")
'''),
("Collecting", "Respawn at checkpoint", "respawn.pawn", "Moves the player back when they fall off the world.", '''# Respawn: falls too far? Go back to the last checkpoint (or the start).

fall_limit = 900   # range 300 3000

local home_x = 0
local home_y = 0

on start
    home_x = self.x
    home_y = self.y

when self.y > fall_limit
    if game.check_x != 0 or game.check_y != 0
        self.x = game.check_x
        self.y = game.check_y
    else
        self.x = home_x
        self.y = home_y
    self.vy = 0
    self.vx = 0
    shake(6, 0.2)
'''),
("Collecting", "Goal (next scene)", "goal.pawn", "Loads another scene when the player touches it.", '''# Goal: touch it to go to the next scene. Tick Trigger. Set the scene name below.

next_scene = "Level 2"

on touch as who
    if who.has_tag("player")
        play("coin")
        load_scene(next_scene)
'''),
("Collecting", "Kill zone", "kill_zone.pawn", "Sends the player back when they touch it (spikes, lava).", '''# Kill zone: tick Trigger. Touching it restarts the scene.

on touch as who
    if who.has_tag("player")
        shake(10, 0.3)
        play("hit")
        wait 0.3 seconds
        load_scene(scene_name())
'''),
("Combat", "Shoot bullets", "shooter.pawn", "Press F or click to fire copies of an object called 'Bullet'.", '''# Shooter: make an object called "Bullet" (untick Active) with the 'Bullet' script, then
# press F or click to shoot.

cooldown = 0.25    # range 0.05 2
bullet_speed = 600

local ready = true

when (pressed("f") or mouse.clicked) and ready
    ready = false
    b = spawn("Bullet", self.x, self.y)
    dir = 1
    if self.flip_x
        dir = -1
    b.vx = dir * bullet_speed
    play("shoot")
    wait cooldown seconds
    ready = true
'''),
("Combat", "Bullet", "bullet.pawn", "Flies straight and disappears after a while or when it hits something.", '''# Bullet: a copy made by the 'Shoot bullets' script. Tick Trigger.
# Anything tagged "enemy" it touches is destroyed.

lifetime = 2

after lifetime seconds
    self.destroy()

on touch as who
    if who.has_tag("enemy")
        who.destroy()
        game.score += 1
        self.destroy()
'''),
("Combat", "Enemy with health", "enemy_health.pawn", "Takes hits from objects tagged 'bullet' and flashes.", '''# Enemy with health: tag this object "enemy". Bullets must be tagged "bullet" and be triggers.

hp = 3             # range 1 20

on touch as who
    if who.has_tag("bullet")
        hp -= 1
        who.destroy()
        shake(3, 0.1)
        self.alpha = 0.3
        wait 0.08 seconds
        self.alpha = 1
        if hp <= 0
            game.score += 5
            self.destroy()
'''),
("Combat", "Contact damage", "contact_damage.pawn", "Hurts the player when touched; they get a moment of safety.", '''# Contact damage: put this on an enemy and tick Trigger. The player is tagged "player".

damage = 1
safe_time = 1.0    # range 0.2 3

local safe = false

on touch as who
    if who.has_tag("player") and not safe
        safe = true
        game.hp -= damage
        shake(8, 0.25)
        play("hit")
        wait safe_time seconds
        safe = false
'''),
("Combat", "Turret", "turret.pawn", "Fires at the player every few seconds when close.", '''# Turret: fires copies of "Bullet" toward the player (tagged "player") when in range.

range_px = 450     # range 100 1200
every_seconds = 1.5

every every_seconds seconds
    target = find("#player")
    if target != none and distance(self, target) < range_px
        b = spawn("Bullet", self.x, self.y)
        if target.x < self.x
            b.vx = -400
        else
            b.vx = 400
'''),
("Effects", "Fade in", "fade_in.pawn", "Starts invisible and fades in.", '''# Fades in when the game starts.

seconds_to_fade = 1.5    # range 0.2 10

on start
    self.alpha = 0
    tween self.alpha to 1 over seconds_to_fade seconds
'''),
("Effects", "Pulse (breathing)", "pulse.pawn", "Grows and shrinks smoothly.", '''# Pulses bigger and smaller.

amount = 0.2       # range 0.05 1
speed = 1.2        # range 0.2 5

local w0 = 0
local h0 = 0

on start
    w0 = self.width
    h0 = self.height
    while true
        tween self.width to w0 * (1 + amount) over speed seconds ease smooth
        tween self.height to h0 * (1 + amount) over speed seconds ease smooth
        wait tweens
        tween self.width to w0 over speed seconds ease smooth
        tween self.height to h0 over speed seconds ease smooth
        wait tweens
'''),
("Effects", "Float up and down", "bob.pawn", "Gently bobs, like a floating coin.", '''# Floats up and down.

height_px = 8      # range 1 60
speed = 2          # range 0.2 8

local base_y = 0
local t = 0

on start
    base_y = self.y

when true
    t += dt * speed
    self.y = base_y + sin(t * 57.3) * height_px
'''),
("Effects", "Particle burst on touch", "burst_touch.pawn", "Pops a Particles object when the player touches it.", '''# Needs a Particles object named "Pop" (untick "Keeps emitting"). Tick Trigger on this object.

on touch as who
    if who.has_tag("player")
        fx = find("Pop")
        if fx != none
            fx.x = self.x
            fx.y = self.y
            fx.burst(25)
        self.destroy()
'''),
("Effects", "Flickering light", "flicker_light.pawn", "Makes a Light flicker like a candle or a broken lamp.", '''# Put this on a Light object (Add > Light).

min_strength = 0.4  # range 0 1
max_strength = 1    # range 0 2

every 0.08 seconds
    self.intensity = random(min_strength, max_strength)
'''),
("Effects", "Scrolling background", "scroll_bg.pawn", "Slowly slides a background object sideways, wrapping around.", '''# Scrolls this object left. Make it wide and put a copy next to it for endless scrolling.

speed = 40         # range -300 300
wrap_width = 960

local start_x = 0

on start
    start_x = self.x

when true
    self.x -= speed * dt
    if self.x < start_x - wrap_width
        self.x = start_x
'''),
("Effects", "Day and night", "day_night.pawn", "Slowly changes the scene's darkness over time.", '''# Day and night cycle using the scene's darkness. Attach to any object.

minutes_per_day = 0.5   # range 0.1 10
night_darkness = 0.75   # range 0.2 1

local t = 0

when true
    t += dt / (minutes_per_day * 60)
    darkness((1 - cos(t * 360)) / 2 * night_darkness)
'''),
("Effects", "Typewriter text", "typewriter.pawn", "Types the words of a Text object one letter at a time.", '''# Types out this Text object's words letter by letter.

letters_per_second = 25   # range 5 100

on start
    full = self.text
    self.text = ""
    n = 0
    while n < len(full)
        n += 1
        self.text = full.slice(0, n)
        wait 1 / letters_per_second seconds
'''),
("Game flow", "Countdown timer", "countdown.pawn", "Counts down in game.time and ends the game at zero. Attach to a Text.", '''# Countdown: shows the time left on this Text object.

start_time = 30    # range 5 300

on start
    game.time = start_time

every 1 seconds
    game.time -= 1
    self.text = "Time: {game.time}"
    if game.time <= 0
        self.text = "Time's up!"
        load_scene(scene_name())
'''),
("Game flow", "Pause menu (Esc)", "pause_menu.pawn", "Esc shows or hides a 'Pause Panel' object and stops time.", '''# Pause: press Escape to show/hide an object called "Pause Panel" (untick Active at the start).
# Other scripts can check game.paused.

when pressed("escape")
    panel = find("Pause Panel")
    game.paused = not game.paused
    if panel != none
        if game.paused
            panel.show()
        else
            panel.hide()
'''),
("Game flow", "Play button", "play_button.pawn", "A Button that loads the first level.", '''# Put this on a Button object (Add > UI > Button).

level = "Level 1"

on click
    play("coin")
    load_scene(level)
'''),
("Game flow", "Save and load buttons", "save_buttons.pawn", "Put on a Button: saves or loads the game depending on its text.", '''# Put on a Button. If the button's text says Save it saves, if it says Load it loads.

slot = "slot1"

on click
    if self.text == "Save"
        save_game(slot)
        print("Saved!")
    else
        if load_game(slot)
            print("Loaded!")
        else
            print("No save found")
'''),
("Game flow", "Volume slider", "volume_slider.pawn", "Put on a Slider to change the music volume.", '''# Put on a Slider object (Add > UI > Slider).

on start
    self.value = get_volume("music")

on change as v
    volume("music", v)
'''),
("Game flow", "Health bar", "health_bar.pawn", "Puts game.hp on a Progress bar.", '''# Put on a Progress bar object. Shows game.hp out of max_hp.

max_hp = 5

on start
    if game.hp == 0
        game.hp = max_hp

when true
    self.value = clamp(game.hp / max_hp, 0, 1)
'''),
("Game flow", "Lives and game over", "lives.pawn", "Counts lives in game.lives and restarts when they run out.", '''# Lives: call  game.lives -= 1  from other scripts (like Kill zone). This script watches it.

start_lives = 3

on start
    if game.lives == 0
        game.lives = start_lives

watch game.lives as n
    if n <= 0
        game.lives = start_lives
        load_scene(scene_name())
'''),
("Game flow", "Enemy states (patrol and chase)", "enemy_states.pawn", "A small state machine: patrol until the player is close, then chase.", '''# Enemy brain with states. The player needs the tag "player".

speed = 90          # range 20 300
sight = 250         # range 50 800

local home_x = 0

on start
    home_x = self.x

state patrol
    on enter
        self.flip_x = false
    every 0.016 seconds
        self.x += speed * 0.016
        if self.x > home_x + 150
            self.flip_x = true
        if self.x < home_x - 150
            self.flip_x = false
    when find("#player") != none and distance(self, find("#player")) < sight
        go chase

state chase
    every 0.016 seconds
        t = find("#player")
        if t == none
            go patrol
        elif t.x > self.x
            self.x += speed * 1.5 * 0.016
        else
            self.x -= speed * 1.5 * 0.016
    when find("#player") == none or distance(self, find("#player")) > sight * 1.6
        go patrol
'''),
("Utility", "Destroy after a while", "lifetime.pawn", "Removes the object after some seconds.", '''# Disappears after a few seconds.

seconds_alive = 3

after seconds_alive seconds
    self.destroy()
'''),
("Utility", "Click counter", "click_counter.pawn", "Counts clicks on this object into game.clicks.", '''# Counts clicks on this object (needs a Button, or any object with an 'on click').

on click
    game.clicks += 1
    print("clicks:", game.clicks)
'''),
("Utility", "Debug watch", "debug_watch.pawn", "Pauses the game with breakpoint() when you press B, so you can inspect it.", '''# Press B while playing to pause and look at the Watch panel (bottom of the editor).
# You can change values there and then continue with F6.

when pressed("b")
    breakpoint("you pressed B")
'''),
]

CATEGORY_OF_BUILTIN = {
    "Platformer movement": "Movement", "Top-down movement": "Movement", "Collectible": "Collecting",
    "Score display": "Game flow", "Blink (uses wait)": "Effects", "Spawner (uses wait)": "Utility",
    "Patrol (uses states)": "Movement", "Spin": "Effects",
}
