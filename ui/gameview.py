"""Game view: runs the game inside the editor (or full-window in the exported player)."""
import os
import time

from PySide6.QtCore import QRectF, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from pawnlang import PawnError
from engine.mixer import Mixer
from engine.glrender import disable_shared, shared_renderer
from engine.render import draw_scene, qcolor
from engine.runtime import Runtime
from .theme import C

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer, QSoundEffect
except Exception:  # sound is optional
    QAudioOutput = QMediaPlayer = QSoundEffect = QMediaDevices = None

KEYMAP = {Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Up: "up", Qt.Key_Down: "down",
          Qt.Key_Space: "space", Qt.Key_Return: "enter", Qt.Key_Enter: "enter", Qt.Key_Escape: "escape",
          Qt.Key_Shift: "shift", Qt.Key_Control: "ctrl", Qt.Key_Tab: "tab"}


def key_name(e):
    k = e.key()
    if k in KEYMAP:
        return KEYMAP[k]
    if Qt.Key_A <= k <= Qt.Key_Z:
        return chr(k).lower()
    if Qt.Key_0 <= k <= Qt.Key_9:
        return chr(k)
    return None


class GameAudio:
    """Sound effects and music for a running game, driven by a Mixer. Silent (and never crashes) without a sound device."""

    MAX_PLAYERS = 12

    def __init__(self, project, parent):
        self.project, self.parent = project, parent
        self.mixer = Mixer(project.audio_levels)
        self._fx, self._players = {}, []
        self._music = self._music_out = None
        self._music_gain = 1.0
        self._silent = None

    def _ok(self):
        if QSoundEffect is None or QMediaDevices is None or os.environ.get("PAWN_NO_SOUND") \
                or QGuiApplication.platformName() in ("offscreen", "minimal"):
            return False
        if self._silent is None:
            self._silent = not QMediaDevices.audioOutputs()
        return not self._silent

    def _apply_music_volume(self):
        try:
            if self._music_out is not None:
                self._music_out.setVolume(self.mixer.effective("music") * self._music_gain)
        except Exception:
            pass

    def tick(self, dt):
        if self.mixer.update(dt) == "stop":
            self.stop_music()
        self._apply_music_volume()

    def play_sound(self, name, vol=1.0):
        if not self._ok():
            return
        path = self.project.sound_path(name)
        if path is None:
            return
        level = self.mixer.effective("sound") * vol
        try:
            if path.suffix.lower() == ".wav":
                fx = self._fx.get(str(path))
                if fx is None:
                    fx = QSoundEffect(self.parent)
                    fx.setSource(QUrl.fromLocalFile(str(path)))
                    self._fx[str(path)] = fx
                fx.setVolume(level)
                fx.play()
            else:
                out = QAudioOutput(self.parent)
                out.setVolume(level)
                player = QMediaPlayer(self.parent)
                player.setAudioOutput(out)
                player.setSource(QUrl.fromLocalFile(str(path)))
                player.play()
                self._players.append((player, out))
                while len(self._players) > self.MAX_PLAYERS:
                    old, old_out = self._players.pop(0)
                    old.stop()
                    old.deleteLater()
                    old_out.deleteLater()
        except Exception:
            pass

    def play_music(self, name, loop=True, vol=1.0):
        if not self._ok():
            return
        path = self.project.music_path(name)
        if path is None:
            return
        try:
            self.stop_music()
            self._music_gain = vol
            self._music_out = QAudioOutput(self.parent)
            self._music = QMediaPlayer(self.parent)
            self._music.setAudioOutput(self._music_out)
            self._music.setSource(QUrl.fromLocalFile(str(path)))
            self._music.setLoops(QMediaPlayer.Loops.Infinite if loop else QMediaPlayer.Loops.Once)
            self._apply_music_volume()
            self._music.play()
        except Exception:
            pass

    def stop_music(self):
        try:
            if self._music is not None:
                self._music.stop()
                self._music.deleteLater()
                self._music_out.deleteLater()
        except Exception:
            pass
        self._music = self._music_out = None

    def pause_music(self):
        try:
            if self._music is not None:
                self._music.pause()
        except Exception:
            pass

    def resume_music(self):
        try:
            if self._music is not None:
                self._music.play()
        except Exception:
            pass

    def music_playing(self):
        try:
            return self._music is not None and self._music.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            return False

    def fade_music(self, target, seconds, stop=False):
        if self.mixer.fade_music(target, seconds, stop) == "stop":
            self.stop_music()

    def stop_all(self):
        self.stop_music()
        for p, o in self._players:
            try:
                p.stop()
            except Exception:
                pass

    def set_volume(self, kind, v):
        self.mixer.set(kind, v)
        self._apply_music_volume()

    def get_volume(self, kind):
        return self.mixer.level[kind]

    def mute(self, on):
        self.mixer.muted = on
        self._apply_music_volume()


class GameView(QWidget):
    error_raised = Signal(object)   # PawnError
    state_changed = Signal()
    break_hit = Signal()

    def __init__(self, project, assets, console, fullscreen_mode=False):
        super().__init__()
        self.project, self.assets, self.console = project, assets, console
        self.rt = None
        self.paused = False
        self.errored = False
        self.timer = QTimer(self, interval=16)
        self.timer.timeout.connect(self._tick)
        self.last = time.perf_counter()
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 200)
        self.audio = GameAudio(project, self)
        self.fullscreen_mode = fullscreen_mode
        from engine.gamepad import XInput
        self.pads = XInput()

    # ---- control --------------------------------------------------------------
    @property
    def running(self):
        return self.rt is not None

    def start(self, scene_dict, scene_name=None):
        self.audio = GameAudio(self.project, self)
        rt = Runtime(scene_dict, self.project, console=self.console, audio=self.audio, scene_name=scene_name)
        rt.start()      # may raise PawnError; caller shows it
        self.restart_scene = (scene_dict, scene_name)
        self._gpu_announced = False
        rt.rumble_fn = self.pads.rumble
        self.rt = rt
        self.paused = False
        self.errored = False
        self.last = time.perf_counter()
        self.timer.start()
        self.setFocus()
        self.state_changed.emit()
        self.update()

    def stop(self):
        self.timer.stop()
        self.audio.stop_all()
        self.rt = None
        self.paused = False
        self.errored = False
        self.state_changed.emit()
        self.update()

    def toggle_pause(self):
        if self.rt:
            self.paused = not self.paused
            self.last = time.perf_counter()
            self.state_changed.emit()
            self.update()

    def resume_after_error(self):
        self.errored = False
        self.paused = False
        self.last = time.perf_counter()
        self.state_changed.emit()

    def step(self):
        if self.rt:
            self._advance(1 / 60)
            self.update()

    def _advance(self, dt):
        try:
            self.rt.update(dt)
            if self.rt is not None and self.rt.break_msg:
                msg, self.rt.break_msg = self.rt.break_msg, None
                self.paused = True
                self.console(msg + ". Look at the Watch panel, then press Pause/Resume (F6) to continue.", "warn")
                self.break_hit.emit()
                self.state_changed.emit()
            if self.rt.restart_requested:
                self.restart()
        except PawnError as e:
            self.paused = self.errored = True
            self.error_raised.emit(e)
            self.state_changed.emit()
        except Exception as e:      # a bug in the engine itself: never crash the editor
            import traceback
            self.console(traceback.format_exc(), "error")
            self.paused = self.errored = True
            self.error_raised.emit(PawnError(f"Internal engine problem: {e}"))
            self.state_changed.emit()

    def restart(self):
        d, name = self.restart_scene
        self.stop()
        self.start(d, name)

    restart_scene = None

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self.last)
        self.last = now
        if self.rt and not self.paused:
            self.rt.set_pads(self.pads.poll())
            self._advance(dt)
        self.update()

    # ---- geometry -----------------------------------------------------------------
    def _metrics(self):
        zoom = self.rt.cam_obj.zoom if self.rt and self.rt.cam_obj else 1.0
        s = min(self.width() / 960.0, self.height() / 540.0)
        view = QRectF(0, 0, 960 * s, 540 * s)
        view.moveCenter(QRectF(self.rect()).center())
        return s, zoom, view

    # ---- painting --------------------------------------------------------------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#0b0c10"))
        f = QFont()
        if not self.rt:
            p.setPen(QColor(C["muted"]))
            f.setPixelSize(16)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "Press  ▶ Play  to run your game here")
            return
        s, zoom, view = self._metrics()
        scene = self.rt.scene
        p.save()
        p.setClipRect(view)
        if not self._paint_gpu(p, scene, s, zoom, view):
            self._paint_cpu(p, scene, s, zoom, view)
        p.restore()
        if self.paused:
            p.fillRect(view, QColor(0, 0, 0, 110))
            f.setPixelSize(22)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(C["red"] if self.errored else C["gold2"]))
            p.drawText(view, Qt.AlignCenter, "Paused on a mistake in your script" if self.errored else "Paused")

    def _paint_cpu(self, p, scene, s, zoom, view):
        """The normal (non-GPU) way to draw the world, with a simpler version of the screen effects."""
        target, q = p, None
        if self.rt.effects:
            from PySide6.QtGui import QImage
            q = QImage(max(2, int(view.width())), max(2, int(view.height())), QImage.Format_ARGB32_Premultiplied)
            target = QPainter(q)
            target.setRenderHint(QPainter.Antialiasing)
            target.setRenderHint(QPainter.SmoothPixmapTransform)
            target.translate(view.width() / 2, view.height() / 2)
        else:
            target.translate(view.center())
        target.fillRect(QRectF(-4000, -4000, 8000, 8000), qcolor(scene.bg)) if q is None else q.fill(qcolor(scene.bg))
        target.scale(s * zoom, s * zoom)
        target.translate(-self.rt.cam[0], -self.rt.cam[1])
        draw_scene(target, scene, self.rt.camv(), self.assets, editor=False)
        if q is not None:
            from engine.effects import apply_cpu
            target.end()
            p.drawImage(view.topLeft(), apply_cpu(q, self.rt.effects, self.rt.time))

    def _paint_gpu(self, p, scene, s, zoom, view):
        """Draw the world on the graphics card. False means 'use the normal renderer instead'."""
        gpu = shared_renderer()
        if gpu is None:
            return False
        dpr = self.devicePixelRatioF()
        try:
            if not self._gpu_announced:
                self._gpu_announced = True
                gpu.reset()
                self.console("Drawing with the graphics card (" + gpu.info + ")", "ok")
            img = gpu.render(scene, self.rt, self.assets, view.width() * dpr, view.height() * dpr, zoom, s * dpr)
        except Exception as e:      # never let a graphics problem stop the game: use the normal renderer
            disable_shared()
            self.console(f"The graphics card path failed ({e}). Using the normal renderer instead.", "warn")
            return False
        img.setDevicePixelRatio(dpr)
        p.drawImage(view.topLeft(), img)
        return True

    _gpu_announced = False

    # ---- input -------------------------------------------------------------------------
    def keyPressEvent(self, e):
        if self.rt and self.rt.ui.focus is not None:       # a text box is being typed into
            k = e.key()
            if k == Qt.Key_Backspace:
                self.rt.typed.append("\b")
            elif k in (Qt.Key_Return, Qt.Key_Enter):
                self.rt.typed.append("\n")
            elif k == Qt.Key_Escape:
                self.rt.ui._set_focus(None)
            elif e.text() and not (e.modifiers() & (Qt.ControlModifier | Qt.AltModifier)):
                self.rt.typed.extend(e.text())
            e.accept()
            return
        n = key_name(e)
        if n and self.rt and not e.isAutoRepeat():
            self.rt.down.add(n)
            self.rt.pressed.add(n)
        if n is None or n in ("left", "right", "up", "down", "space"):
            e.accept()
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        n = key_name(e)
        if n and self.rt and not e.isAutoRepeat():
            self.rt.down.discard(n)

    def focusOutEvent(self, e):
        if self.rt:
            self.rt.down.clear()
        super().focusOutEvent(e)

    def _mouse(self, e):
        if not self.rt:
            return
        s, zoom, view = self._metrics()
        pos = e.position()
        self.rt.mx = (pos.x() - view.center().x()) / (s * zoom) + self.rt.cam[0]
        self.rt.my = (pos.y() - view.center().y()) / (s * zoom) + self.rt.cam[1]

    def mouseMoveEvent(self, e):
        self._mouse(e)

    def mousePressEvent(self, e):
        self.setFocus()
        self._mouse(e)
        if self.rt and e.button() == Qt.LeftButton:
            self.rt.mouse_down = True

    def mouseReleaseEvent(self, e):
        if self.rt:
            self.rt.mouse_down = False
