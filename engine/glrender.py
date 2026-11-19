"""GPU world renderer (OpenGL 3.3).

The world is drawn on the graphics card and handed back as a picture, so it plugs into the normal Qt window:

* **Instancing**: every rectangle, circle, sprite, tile and particle is one entry in a list; the card draws a whole
  run of them with a single call.
* **Static batching**: a tilemap's tiles are packed once and kept on the card until a tile changes.
* **Texture atlas**: all sprite pictures live on a few big textures, so the card rarely switches textures.
* **Culling**: things outside the camera are never sent.
* **Lighting**: darkness and lights are a shader, not a painted picture.

Things the card can't draw yet (text, buttons and other UI, polygons) are painted with QPainter into a layer that is
put into the right place in the drawing order, so everything still stacks exactly like the normal renderer.
If anything goes wrong, `make_renderer()` returns None and the game keeps using the normal renderer.
"""
from shiboken6 import VoidPtr
import math
import os
import random
from array import array

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QImage, QOffscreenSurface, QOpenGLContext, QPainter, QSurfaceFormat)
from PySide6.QtOpenGL import (QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat, QOpenGLFunctions_3_3_Core,
                              QOpenGLShaderProgram, QOpenGLShader, QOpenGLTexture, QOpenGLVersionFunctionsFactory,
                              QOpenGLVersionProfile)

from . import joints, particles, tilemap
from .gameobject import UI_KINDS
from .render import _is_overlay, _source_rect, draw_object, qcolor, spring_points
from .animation import cell_count
from .scene import sort_for_drawing

GL_FLOAT, GL_TRIANGLE_STRIP, GL_BLEND, GL_ONE, GL_ONE_MINUS_SRC_ALPHA = 0x1406, 0x0005, 0x0BE2, 1, 0x0303
GL_COLOR_BUFFER_BIT, GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_DYNAMIC_DRAW = 0x4000, 0x8892, 0x88E4, 0x88E8
GL_VIEWPORT = 0x0BA2

FLOATS = 16                # numbers per instance
ATLAS_SIZE = 2048
GPU_KINDS = ("rect", "circle", "sprite", "tilemap", "particles")
NOTHING_IN_GAME = ("light", "camera", "empty", "model", "folder", "zone", "spawn", "beam")

VERT = """
#version 330 core
layout(location = 0) in vec2 corner;                 // -0.5 .. 0.5
layout(location = 1) in vec4 a_box;                  // x y w h
layout(location = 2) in vec4 a_misc;                 // angle, flip, kind, radius
layout(location = 3) in vec4 a_color;
layout(location = 4) in vec4 a_uv;
uniform vec2 u_cam;
uniform float u_scale;
uniform vec2 u_size;
uniform vec2 u_origin;
out vec2 v_local;
out vec2 v_uv;
out vec4 v_color;
out vec2 v_half;
flat out vec2 v_misc;
void main() {
    vec2 p = corner * a_box.zw;
    float c = cos(a_misc.x), s = sin(a_misc.x);
    p = vec2(p.x * c - p.y * s, p.x * s + p.y * c);
    vec2 world = a_box.xy + u_origin + p;
    vec2 px = (world - u_cam) * u_scale + u_size * 0.5;
    gl_Position = vec4(px.x / u_size.x * 2.0 - 1.0, 1.0 - px.y / u_size.y * 2.0, 0.0, 1.0);
    v_local = corner * a_box.zw;
    v_half = a_box.zw * 0.5;
    vec2 t = corner + 0.5;
    t.x = a_misc.y < 0.0 ? 1.0 - t.x : t.x;
    v_uv = mix(a_uv.xy, a_uv.zw, t);
    v_color = a_color;
    v_misc = a_misc.zw;
}
"""

FRAG = """
#version 330 core
in vec2 v_local;
in vec2 v_uv;
in vec4 v_color;
in vec2 v_half;
flat in vec2 v_misc;
uniform sampler2D u_tex;
uniform float u_scale;
uniform float u_opacity;
out vec4 frag;
float circle_cover(float aa) {
    vec2 n = v_local / max(v_half, vec2(0.0001));
    float d = (length(n) - 1.0) * min(v_half.x, v_half.y);
    return clamp(0.5 - d / aa, 0.0, 1.0);
}
void main() {
    float kind = v_misc.x;
    float aa = 1.0 / max(u_scale, 0.001);
    if (kind > 5.5) {                                // glowing picture (colors add up)
        vec4 t = texture(u_tex, v_uv);
        frag = vec4(t.rgb * v_color.rgb * v_color.a * u_opacity, 0.0);
    } else if (kind > 4.5) {                         // glowing circle
        float c = circle_cover(aa);
        frag = vec4(v_color.rgb * v_color.a * c * u_opacity, 0.0);
    } else if (kind > 3.5) {                         // full-layer picture (painted by QPainter), already premultiplied
        frag = texture(u_tex, v_uv) * v_color.a * u_opacity;
    } else if (kind > 1.5 && kind < 2.5) {           // picture, tinted by the color
        vec4 t = texture(u_tex, v_uv);
        frag = vec4(t.rgb * v_color.rgb, t.a) * v_color.a * u_opacity;
    } else if (kind > 2.5) {                         // tile: a plain square
        frag = vec4(v_color.rgb * v_color.a, v_color.a) * u_opacity;
    } else if (kind < 0.5) {                         // rounded rectangle
        float r = min(v_misc.y, min(v_half.x, v_half.y));
        vec2 q = abs(v_local) - (v_half - vec2(r));
        float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
        float c = clamp(0.5 - d / aa, 0.0, 1.0);
        frag = vec4(v_color.rgb * v_color.a * c, v_color.a * c) * u_opacity;
    } else {                                         // circle / ellipse
        float c = circle_cover(aa);
        frag = vec4(v_color.rgb * v_color.a * c, v_color.a * c) * u_opacity;
    }
}
"""

DARK_VERT = """
#version 330 core
layout(location = 0) in vec2 corner;
out vec2 v_px;
uniform vec2 u_size;
void main() {
    v_px = (corner + 0.5) * u_size;
    gl_Position = vec4(corner.x * 2.0, -corner.y * 2.0, 0.0, 1.0);
}
"""

DARK_FRAG = """
#version 330 core
in vec2 v_px;
uniform vec4 u_ambient;                 // rgb, darkness
uniform float u_count;
uniform vec4 u_lights[48];              // x y radius intensity   (screen pixels)
out vec4 frag;
float falloff(float t) {                // 1 in the middle, 0.75 at 55%, 0 at the edge
    if (t >= 1.0) return 0.0;
    if (t < 0.55) return mix(1.0, 0.75, t / 0.55);
    return mix(0.75, 0.0, (t - 0.55) / 0.45);
}
void main() {
    float a = u_ambient.a;
    for (int i = 0; i < 48; i++) {
        if (float(i) >= u_count) break;
        vec4 L = u_lights[i];
        float t = length(v_px - L.xy) / max(L.z, 1.0);
        a *= 1.0 - clamp(L.w * falloff(t), 0.0, 1.0);
    }
    frag = vec4(u_ambient.rgb * a, a);
}
"""

GLOW_FRAG = """
#version 330 core
in vec2 v_px;
uniform vec4 u_light;                   // x y radius strength
uniform vec3 u_color;
out vec4 frag;
void main() {
    float t = clamp(length(v_px - u_light.xy) / max(u_light.z, 1.0), 0.0, 1.0);
    float a = u_light.w * (1.0 - t);
    frag = vec4(u_color * a, a);
}
"""


_GL = [None]            # the OpenGL functions of the active renderer


def _u(prog, name, *values):
    """Set a shader value by name (PySide needs the numeric location)."""
    loc = prog.uniformLocation(name)
    if loc < 0:
        return
    gl = _GL[0]                                # the plain OpenGL calls behave the same everywhere
    {1: gl.glUniform1f, 2: gl.glUniform2f, 3: gl.glUniform3f, 4: gl.glUniform4f}[len(values)](
        loc, *[float(v) for v in values])


POST_FRAG = """
#version 330 core
in vec2 v_px;
uniform sampler2D u_src;
uniform vec2 u_size;
uniform float u_time;
uniform float u_pixel;
uniform float u_blur;
uniform float u_wave;
uniform float u_aber;
uniform vec4 u_tint;                  // rgb, amount
uniform float u_vig;
uniform float u_gray;
uniform float u_invert;
uniform float u_scan;
out vec4 frag;
vec3 fetch(vec2 px) {
    px = clamp(px, vec2(0.5), u_size - vec2(0.5));
    return texture(u_src, vec2(px.x / u_size.x, 1.0 - px.y / u_size.y)).rgb;
}
void main() {
    vec2 p = v_px;
    if (u_wave > 0.0) p.x += sin(p.y * 0.05 + u_time * 4.0) * u_wave;
    if (u_pixel > 1.0) p = (floor(p / u_pixel) + 0.5) * u_pixel;
    vec3 c;
    if (u_blur > 0.0) {
        c = vec3(0.0);
        float total = 0.0;
        for (int i = -2; i <= 2; i++) {
            for (int j = -2; j <= 2; j++) {
                float w = 1.0 / (1.0 + float(i * i + j * j));
                c += fetch(p + vec2(float(i), float(j)) * u_blur * 0.5) * w;
                total += w;
            }
        }
        c /= total;
    } else if (u_aber > 0.0) {
        c = vec3(fetch(p + vec2(u_aber, 0.0)).r, fetch(p).g, fetch(p - vec2(u_aber, 0.0)).b);
    } else {
        c = fetch(p);
    }
    float lum = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(c, vec3(lum), u_gray);
    c = mix(c, 1.0 - c, u_invert);
    c = mix(c, u_tint.rgb, u_tint.a);
    vec2 q = v_px / u_size - 0.5;
    c *= 1.0 - u_vig * smoothstep(0.25, 0.75, length(q * vec2(1.0, 0.8)) * 1.35);
    if (u_scan > 0.0) c *= 1.0 - u_scan * 0.5 * (0.5 + 0.5 * sin(v_px.y * 3.14159));
    frag = vec4(clamp(c, 0.0, 1.0), 1.0);
}
"""


class Atlas:
    """Sprite pictures packed onto 2048 x 2048 pages. Each picture keeps a 1 pixel border so edges don't bleed."""

    def __init__(self):
        self.pages = []          # [QOpenGLTexture, QImage, shelf_x, shelf_y, shelf_h]
        self.where = {}          # key -> (page, u0, v0, u1, v1, width, height)
        self.dirty = set()

    def add(self, key, image):
        if key in self.where:
            return self.where[key]
        img = image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)
        w, h = img.width(), img.height()
        if w + 2 > ATLAS_SIZE or h + 2 > ATLAS_SIZE:
            img = img.scaled(min(w, ATLAS_SIZE - 2), min(h, ATLAS_SIZE - 2), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            w, h = img.width(), img.height()
        pw, ph = w + 2, h + 2
        for idx, pg in enumerate(self.pages):
            spot = self._fit(pg, pw, ph)
            if spot:
                return self._place(key, idx, spot, img)
        self.pages.append([None, QImage(ATLAS_SIZE, ATLAS_SIZE, QImage.Format_RGBA8888_Premultiplied), 0, 0, 0])
        self.pages[-1][1].fill(0)
        return self._place(key, len(self.pages) - 1, self._fit(self.pages[-1], pw, ph), img)

    @staticmethod
    def _fit(pg, pw, ph):
        x, y, rowh = pg[2], pg[3], pg[4]
        if x + pw > ATLAS_SIZE:
            x, y, rowh = 0, y + rowh, 0
        if y + ph > ATLAS_SIZE:
            return None
        return x, y, max(rowh, ph)

    def _place(self, key, idx, spot, img):
        x, y, rowh = spot
        pg = self.pages[idx]
        w, h = img.width(), img.height()
        p = QPainter(pg[1])
        p.setCompositionMode(QPainter.CompositionMode_Source)
        for dx in (-1, 0, 1):                       # extrude the edge pixels into the border
            for dy in (-1, 0, 1):
                p.drawImage(x + 1 + dx, y + 1 + dy, img)
        p.drawImage(x + 1, y + 1, img)
        p.end()
        pg[2], pg[3], pg[4] = x + w + 2, y, rowh
        self.dirty.add(idx)
        s = float(ATLAS_SIZE)
        self.where[key] = (idx, (x + 1) / s, (y + 1) / s, (x + 1 + w) / s, (y + 1 + h) / s, w, h)
        return self.where[key]

    def texture(self, idx):
        pg = self.pages[idx]
        if pg[0] is None or idx in self.dirty:
            if pg[0] is not None:
                pg[0].destroy()
            t = QOpenGLTexture(pg[1].copy(), QOpenGLTexture.DontGenerateMipMaps)
            t.setMinMagFilters(QOpenGLTexture.Linear, QOpenGLTexture.Linear)
            t.setWrapMode(QOpenGLTexture.ClampToEdge)
            pg[0] = t
            self.dirty.discard(idx)
        return pg[0]

    def clear(self):
        for pg in self.pages:
            if pg[0] is not None:
                pg[0].destroy()
        self.pages, self.where, self.dirty = [], {}, set()


class GLRenderer:
    def __init__(self):
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        self.ctx = QOpenGLContext()
        self.ctx.setFormat(fmt)
        if not self.ctx.create():
            raise RuntimeError("OpenGL 3.3 is not available")
        self.surface = QOffscreenSurface()
        self.surface.setFormat(self.ctx.format())
        self.surface.create()
        if not self.ctx.makeCurrent(self.surface):
            raise RuntimeError("Could not use OpenGL")
        self.gl = QOpenGLVersionFunctionsFactory.get(QOpenGLVersionProfile(fmt), self.ctx)
        if self.gl is None:
            raise RuntimeError("OpenGL 3.3 functions are missing")
        self.gl.initializeOpenGLFunctions()
        _GL[0] = self.gl
        self.info = "OpenGL " + str(self.gl.glGetString(0x1F02))
        self.prog = self._program(VERT, FRAG)
        self.dark = self._program(DARK_VERT, DARK_FRAG)
        self.glow = self._program(DARK_VERT, GLOW_FRAG)
        self.post = self._program(DARK_VERT, POST_FRAG)
        self.fbo2 = None
        self._make_geometry()
        self.atlas = Atlas()
        self.fbo = None
        self.size = (0, 0)
        self.stats = {"draw_calls": 0, "instances": 0, "uploaded": 0}
        self.static = {}                       # tilemap object id -> (stamp, vbo, vao, count, object, atlas page)
        self._reset = False
        self.layer = None
        self.layer_tex = None
        self.ctx.doneCurrent()

    # ---- setup -------------------------------------------------------------------------
    def _program(self, vs, fs):
        p = QOpenGLShaderProgram()
        if not p.addShaderFromSourceCode(QOpenGLShader.Vertex, vs) or not p.addShaderFromSourceCode(QOpenGLShader.Fragment, fs):
            raise RuntimeError("Shader problem: " + p.log())
        if not p.link():
            raise RuntimeError("Shader link problem: " + p.log())
        return p

    def _make_geometry(self):
        gl = self.gl
        quad = array("f", [-0.5, -0.5, 0.5, -0.5, -0.5, 0.5, 0.5, 0.5])
        from PySide6.QtOpenGL import QOpenGLBuffer, QOpenGLVertexArrayObject
        self.quad_buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self.quad_buf.create()
        self.quad_buf.bind()
        self.quad_buf.allocate(quad.tobytes(), len(quad) * 4)
        self.inst_buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self.inst_buf.create()
        self.inst_buf.setUsagePattern(QOpenGLBuffer.DynamicDraw)
        self.vao = QOpenGLVertexArrayObject()
        self.vao.create()
        self.vao.bind()
        self.quad_buf.bind()
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, GL_FLOAT, 0, 8, VoidPtr(0))
        self._bind_instance_layout(self.inst_buf)
        self.vao.release()
        self.dark_vao = QOpenGLVertexArrayObject()
        self.dark_vao.create()
        self.dark_vao.bind()
        self.quad_buf.bind()
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, GL_FLOAT, 0, 8, VoidPtr(0))
        self.dark_vao.release()

    def _bind_instance_layout(self, buf):
        gl = self.gl
        buf.bind()
        for loc, off in ((1, 0), (2, 16), (3, 32), (4, 48)):
            gl.glEnableVertexAttribArray(loc)
            gl.glVertexAttribPointer(loc, 4, GL_FLOAT, 0, FLOATS * 4, VoidPtr(off))
            gl.glVertexAttribDivisor(loc, 1)

    def _make_static_vao(self, buf):
        from PySide6.QtOpenGL import QOpenGLVertexArrayObject
        vao = QOpenGLVertexArrayObject()
        vao.create()
        vao.bind()
        self.quad_buf.bind()
        self.gl.glEnableVertexAttribArray(0)
        self.gl.glVertexAttribPointer(0, 2, GL_FLOAT, 0, 8, VoidPtr(0))
        self._bind_instance_layout(buf)
        vao.release()
        return vao

    # ---- one frame ---------------------------------------------------------------------------
    def render(self, scene, rt, assets, width, height, zoom=1.0, scale=1.0):
        """Draw the scene as the game camera sees it. `scale` is pixels per world unit (before zoom).

        Returns a QImage (premultiplied ARGB32) of width x height.
        """
        width, height = max(2, int(width)), max(2, int(height))
        if not self.ctx.makeCurrent(self.surface):
            raise RuntimeError("Lost the OpenGL context")
        try:
            if self._reset:
                self._reset = False
                self.atlas.clear()
                for entry in self.static.values():
                    entry[1].destroy()
                self.static = {}
            return self._render(scene, rt, assets, width, height, zoom * scale)
        finally:
            self.ctx.doneCurrent()

    def _ensure_target(self, w, h):
        if self.fbo is None or self.size != (w, h):
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.NoAttachment)
            self.fbo = QOpenGLFramebufferObject(w, h, fmt)
            self.fbo2 = None
            self.size = (w, h)
            self.layer = QImage(w, h, QImage.Format_RGBA8888_Premultiplied)
            if self.layer_tex is not None:
                self.layer_tex.destroy()
                self.layer_tex = None

    def _render(self, scene, rt, assets, w, h, scale):
        gl = self.gl
        self._ensure_target(w, h)
        self.fbo.bind()
        gl.glViewport(0, 0, w, h)
        bg = QColor(qcolor(scene.bg))
        gl.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1.0)
        gl.glClear(GL_COLOR_BUFFER_BIT)
        gl.glEnable(GL_BLEND)
        gl.glBlendFunc(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)
        self.stats = {"draw_calls": 0, "instances": 0, "uploaded": 0}
        cam = rt.camv()
        cx, cy = rt.cam[0], rt.cam[1]
        self.view = (cx, cy, scale, w, h)
        self.cam_v = cam
        self.scene = scene
        self.assets = assets
        objs = sort_for_drawing(scene)
        dark = scene.darkness > 0
        for overlay in ((False, True) if dark else (None,)):
            if overlay:
                self._darkness(scene, cam)
            self._draw_objects(objs, overlay)
        fx = getattr(rt, "effects", None)
        target = self.fbo
        if fx:
            target = self._post(fx, rt, w, h)
        img = target.toImage()                  # one read-back of the finished picture
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)

    def _post(self, fx, rt, w, h):
        """Screen effects: blur, pixelate, tint and friends, done by a shader over the finished picture."""
        gl = self.gl
        if self.fbo2 is None:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.NoAttachment)
            self.fbo2 = QOpenGLFramebufferObject(w, h, fmt)
        self.fbo2.bind()
        gl.glViewport(0, 0, w, h)
        gl.glDisable(GL_BLEND)
        p = self.post
        p.bind()
        s = w / 960.0                          # effect sizes are given for a 960 wide picture
        tint = fx.get("tint", (None, 0.0))
        tc = qcolor(tint[0]) if tint[0] else QColor(0, 0, 0)
        _u(p, "u_size", float(w), float(h))
        _u(p, "u_time", float(rt.time))
        _u(p, "u_pixel", float(fx.get("pixelate", 0.0)) * s)
        _u(p, "u_blur", float(fx.get("blur", 0.0)) * s)
        _u(p, "u_wave", float(fx.get("wave", 0.0)) * s)
        _u(p, "u_aber", float(fx.get("aberration", 0.0)) * s)
        _u(p, "u_tint", tc.redF(), tc.greenF(), tc.blueF(), float(tint[1]))
        _u(p, "u_vig", float(fx.get("vignette", 0.0)))
        _u(p, "u_gray", float(fx.get("grayscale", 0.0)))
        _u(p, "u_invert", float(fx.get("invert", 0.0)))
        _u(p, "u_scan", float(fx.get("scanlines", 0.0)))
        gl.glActiveTexture(0x84C0)
        gl.glBindTexture(0x0DE1, self.fbo.texture())
        self.dark_vao.bind()
        gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self.dark_vao.release()
        self.stats["draw_calls"] += 1
        return self.fbo2

    # ---- objects ------------------------------------------------------------------------------
    def _draw_objects(self, objs, overlay):
        cx, cy, scale, w, h = self.view
        half_w, half_h = w / scale / 2 + 4, h / scale / 2 + 4
        batch = array("f")
        batch_page = [None]
        cpu_run = []

        def flush_gpu():
            if batch:
                self._draw_instances(batch, batch_page[0])
                del batch[:]
            batch_page[0] = None

        def flush_cpu():
            if cpu_run:
                self._draw_cpu(cpu_run)
                del cpu_run[:]

        for o in objs:
            if o.dead:
                continue
            if overlay is not None and _is_overlay(o) != overlay:
                continue
            active = o.is_active()
            if not active:
                continue
            opacity = max(0.0, min(1.0, o.alpha))
            if opacity <= 0.0:
                continue
            k = o.kind
            if k in NOTHING_IN_GAME:
                continue
            x, y = o.world_pos(self.cam_v)
            gpu_ok = k in GPU_KINDS and not (k == "tilemap" and (o.angle or o.flip_x))
            if gpu_ok and k == "sprite":
                pm = self.assets.pixmap(o.sprite) if self.assets else None
                gpu_ok = pm is not None and not pm.isNull()
            if gpu_ok:
                if k != "tilemap" and k != "particles":
                    reach = max(o.w, o.h) * 0.75 + 2
                    if abs(x - cx) > half_w + reach or abs(y - cy) > half_h + reach:
                        continue
                flush_cpu()
                if k in ("rect", "circle"):
                    if batch_page[0] not in (None, -1):
                        flush_gpu()
                    batch_page[0] = -1
                    self._add_shape(batch, o, x, y, opacity)
                elif k == "sprite":
                    self._add_sprite(batch, batch_page, flush_gpu, o, x, y, opacity)
                elif k == "particles":
                    picture = self._particle_picture(o)
                    if batch_page[0] is not None and batch_page[0] != picture[0]:
                        flush_gpu()
                    batch_page[0] = picture[0]
                    self._add_particles(batch, o, x, y, opacity, picture)
                elif k == "tilemap":
                    flush_gpu()
                    self._draw_tilemap(o, x, y, opacity)
            else:
                flush_gpu()
                cpu_run.append((o, opacity))
        if overlay is not True:
            flush_cpu()
            if batch_page[0] not in (None, -1):
                flush_gpu()
            batch_page[0] = -1
            self._add_joints(batch)
        flush_gpu()
        flush_cpu()

    def _add_joints(self, batch):
        """Ropes, springs and beams as thin rotated rectangles."""
        def seg(x1, y1, x2, y2, width, c):
            d = math.hypot(x2 - x1, y2 - y1)
            if d > 0.01:
                batch.extend(((x1 + x2) / 2, (y1 + y2) / 2, d, width, math.atan2(y2 - y1, x2 - x1), 1.0, 3.0, 0.0,
                              c.redF(), c.greenF(), c.blueF(), c.alphaF(), 0.0, 0.0, 0.0, 0.0))
        for ax, ay, bx, by, width, color, style in joints.lines(self.scene):
            c = qcolor(color)
            if style == "spring":
                pts = spring_points(ax, ay, bx, by)
                for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                    seg(x1, y1, x2, y2, width, c)
            else:
                seg(ax, ay, bx, by, width, c)

    def _add_shape(self, batch, o, x, y, opacity):
        c = qcolor(o.color)
        batch.extend((x, y, o.w, o.h, math.radians(o.angle) if o.angle else 0.0, -1.0 if o.flip_x else 1.0,
                      0.0 if o.kind == "rect" else 1.0, 6.0, c.redF(), c.greenF(), c.blueF(), c.alphaF() * opacity,
                      0.0, 0.0, 0.0, 0.0))

    def _atlas_entry(self, path):
        pm = self.assets.pixmap(path)
        key = (path, pm.cacheKey())             # a changed picture on disk is a new entry
        info = self.atlas.where.get(key)
        if info is None:
            info = self.atlas.add(key, pm.toImage())
        return info

    def _add_sprite(self, batch, batch_page, flush_gpu, o, x, y, opacity):
        info = self._atlas_entry(o.sprite)
        page, u0, v0, u1, v1, iw, ih = info
        if batch_page[0] != page:
            flush_gpu()
            batch_page[0] = page
        cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
        if cols * rows > 1:
            cw, ch = (u1 - u0) / cols, (v1 - v0) / rows
            n = cell_count(o)
            f = int(o.frame) % n if n else 0
            su0, sv0 = u0 + (f % cols) * cw, v0 + (f // cols) * ch
            u0, v0, u1, v1 = su0, sv0, su0 + cw, sv0 + ch
        batch.extend((x, y, o.w, o.h, math.radians(o.angle) if o.angle else 0.0, -1.0 if o.flip_x else 1.0,
                      2.0, 0.0, 1.0, 1.0, 1.0, opacity, u0, v0, u1, v1))
        return page

    def _particle_picture(self, o):
        """(atlas page, uv rectangle, (columns, rows)) when the particles are pictures, else (-1, ..)."""
        if o.sprite and self.assets:
            pm = self.assets.pixmap(o.sprite)
            if pm is not None and not pm.isNull():
                page, u0, v0, u1, v1, _w, _h = self._atlas_entry(o.sprite)
                return page, (u0, v0, u1, v1), (max(1, o.sheet_cols), max(1, o.sheet_rows))
        return -1, (0.0, 0.0, 1.0, 1.0), (1, 1)

    def _add_particles(self, batch, o, x, y, opacity, picture):
        if not o.parts:
            return
        _page, uv, sheet = picture
        look = particles.look(o, opacity, uv, sheet)
        if picture[0] < 0 and look[10] >= 2.0 and look[10] != 5.0:
            look[10] = 5.0 if o.em_add else 1.0                 # picture missing: draw plain dots
        batch.extend(particles.pack(o.parts, look, x if o.em_local else 0.0, y if o.em_local else 0.0))

    def _draw_tilemap(self, o, x, y, opacity):
        ts = float(o.tile_size)
        c = qcolor(o.color)
        info = self._atlas_entry(o.sprite) if o.sprite and self.assets and self.assets.pixmap(o.sprite) else None
        stamp = (o.tile_ver, len(o.tiles), ts, o.sprite, o.sheet_cols, o.sheet_rows, o.color, info is not None)
        cached = self.static.get(id(o))
        if cached is None or cached[0] != stamp or cached[4] is not o:
            data = array("f")
            cols, rows = max(1, o.sheet_cols), max(1, o.sheet_rows)
            n_cells = cols * rows
            for key, n in o.tiles.items():
                col, row = tilemap.split(key)
                if info:
                    page, u0, v0, u1, v1, iw, ih = info
                    cw, ch = (u1 - u0) / cols, (v1 - v0) / rows
                    i = n % n_cells
                    su, sv = u0 + (i % cols) * cw, v0 + (i // cols) * ch
                    data.extend((col * ts, row * ts, ts, ts, 0.0, 1.0, 2.0, 0.0, 1.0, 1.0, 1.0, 1.0, su, sv, su + cw, sv + ch))
                else:
                    shade = min(120, 25 * (n % 6)) / 255.0 if n else 0.0
                    r, g, b = c.redF() * (1 - shade * 0.47), c.greenF() * (1 - shade * 0.47), c.blueF() * (1 - shade * 0.47)
                    data.extend((col * ts, row * ts, ts, ts, 0.0, 1.0, 3.0, 0.0, r, g, b, c.alphaF(), 0.0, 0.0, 0.0, 0.0))
            if cached is not None:
                cached[1].destroy()
            from PySide6.QtOpenGL import QOpenGLBuffer
            buf = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
            buf.create()
            buf.bind()
            buf.allocate(data.tobytes(), len(data) * 4)
            vao = self._make_static_vao(buf)
            cached = (stamp, buf, vao, len(data) // FLOATS, o, info[0] if info else None)
            self.static[id(o)] = cached
            self.stats["uploaded"] += len(data) // FLOATS
        stamp, buf, vao, count, _o, page = cached
        if count:
            self._use_program(opacity, x, y, page)
            vao.bind()
            self.gl.glDrawArraysInstanced(GL_TRIANGLE_STRIP, 0, 4, count)
            vao.release()
            self.stats["draw_calls"] += 1
            self.stats["instances"] += count

    def _use_program(self, opacity, ox=0.0, oy=0.0, page=None):
        cx, cy, scale, w, h = self.view
        p = self.prog
        p.bind()
        _u(p, "u_cam", float(cx), float(cy))
        _u(p, "u_scale", float(scale))
        _u(p, "u_size", float(w), float(h))
        _u(p, "u_origin", float(ox), float(oy))
        _u(p, "u_opacity", float(opacity))
        if page is not None and page >= 0:
            self.gl.glActiveTexture(0x84C0)
            self.atlas.texture(page).bind()

    def _draw_instances(self, batch, page):
        n = len(batch) // FLOATS
        if not n:
            return
        self._use_program(1.0, 0.0, 0.0, page)
        self.vao.bind()
        self.inst_buf.bind()
        data = batch.tobytes()
        self.inst_buf.allocate(data, len(data))
        self.gl.glDrawArraysInstanced(GL_TRIANGLE_STRIP, 0, 4, n)
        self.vao.release()
        self.stats["draw_calls"] += 1
        self.stats["instances"] += n

    # ---- things painted by QPainter, placed in the right spot of the drawing order ----------
    def _draw_cpu(self, run):
        cx, cy, scale, w, h = self.view
        img = self.layer
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.translate(w / 2.0, h / 2.0)
        p.scale(scale, scale)
        p.translate(-cx, -cy)
        for o, opacity in run:
            p.setOpacity(opacity)
            draw_object(p, o, self.cam_v, self.assets, False)
            p.setOpacity(1.0)
        p.end()
        if self.layer_tex is not None:
            self.layer_tex.destroy()
        self.layer_tex = QOpenGLTexture(img, QOpenGLTexture.DontGenerateMipMaps)
        self.layer_tex.setMinMagFilters(QOpenGLTexture.Nearest, QOpenGLTexture.Nearest)
        self.layer_tex.setWrapMode(QOpenGLTexture.ClampToEdge)
        self._use_program(1.0)
        self.gl.glActiveTexture(0x84C0)
        self.layer_tex.bind()
        quad = array("f", [cx, cy, w / scale, h / scale, 0.0, 1.0, 4.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0])
        self.vao.bind()
        self.inst_buf.bind()
        self.inst_buf.allocate(quad.tobytes(), len(quad) * 4)
        self.gl.glDrawArraysInstanced(GL_TRIANGLE_STRIP, 0, 4, 1)
        self.vao.release()
        self.stats["draw_calls"] += 1

    # ---- lighting --------------------------------------------------------------------------
    def _darkness(self, scene, cam):
        cx, cy, scale, w, h = self.view
        lights = [o for o in scene.all() if o.kind == "light" and not o.dead and o.is_active()]
        amb = QColor(qcolor(scene.ambient))
        dk = scene.darkness
        data = []
        glows = []
        for o in lights[:48]:
            x, y = o.world_pos(cam)
            r = max(1.0, o.w / 2)
            k = max(0.0, min(1.0, o.intensity * (1.0 - o.flicker * random.random() * 0.5)))
            sx, sy = (x - cx) * scale + w / 2.0, (y - cy) * scale + h / 2.0
            data.append((sx, sy, r * scale, k))
            if o.color.lower() not in ("#ffffff", "#fff"):
                glows.append((sx, sy, r * scale, 0.22 * min(1.0, o.intensity), qcolor(o.color)))
        p = self.dark
        p.bind()
        _u(p, "u_size", float(w), float(h))
        _u(p, "u_ambient", amb.redF(), amb.greenF(), amb.blueF(), float(dk))
        _u(p, "u_count", float(len(data)))
        for i, (a, b, c, d) in enumerate(data):
            _u(p, f"u_lights[{i}]", a, b, c, d)
        self.dark_vao.bind()
        self.gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        self.stats["draw_calls"] += 1
        g = self.glow
        g.bind()
        _u(g, "u_size", float(w), float(h))
        for sx, sy, r, s, col in glows:
            _u(g, "u_light", sx, sy, r, s)
            _u(g, "u_color", col.redF(), col.greenF(), col.blueF())
            self.gl.glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            self.stats["draw_calls"] += 1
        self.dark_vao.release()


    def reset(self):
        """Forget cached pictures and tile batches (called when a game starts)."""
        self._reset = True


_shared = {"renderer": None, "tried": False}


def shared_renderer():
    """The one renderer every game view uses. None if the GPU path isn't available."""
    if not _shared["tried"]:
        _shared["tried"] = True
        _shared["renderer"] = make_renderer()
    return _shared["renderer"]


def disable_shared():
    """Stop using the GPU renderer for the rest of this run (after an error)."""
    _shared["renderer"], _shared["tried"] = None, True


def make_renderer():
    """A GLRenderer, or None when the graphics card can't do it (or PAWN_RENDERER=cpu). Never raises."""
    if os.environ.get("PAWN_RENDERER", "auto").lower() == "cpu":
        return None
    try:
        return GLRenderer()
    except Exception as e:  # any problem at all: use the normal renderer
        if os.environ.get("PAWN_DEBUG"):
            print("GPU renderer unavailable:", e)
        return None
