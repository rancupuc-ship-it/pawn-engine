"""Screen effects: blur, pixelate, tint, vignette and friends. Set from scripts with effect(); drawn by the GPU renderer
(and a simpler version for the normal renderer)."""
from pawnlang import PawnError

# name: (largest value, what the number means)
NUMERIC = {"blur": (20.0, "how many pixels to blur"), "pixelate": (64.0, "size of the big pixels"),
           "vignette": (1.0, "how dark the corners get, 0 to 1"), "grayscale": (1.0, "0 = color, 1 = black and white"),
           "invert": (1.0, "0 = normal, 1 = inverted colors"), "scanlines": (1.0, "strength of the lines, 0 to 1"),
           "aberration": (30.0, "how far the colors split apart"), "wave": (40.0, "how wobbly the picture is")}
NAMES = tuple(NUMERIC) + ("tint",)


def set_effect(effects, name, a=1.0, b=None):
    name = str(name)
    if name not in NAMES:
        from pawnlang import suggest
        raise PawnError(f"There is no screen effect called '{name}'.", hint=suggest(name, list(NAMES)) or "try: " + ", ".join(NAMES))
    if name == "tint":
        if not isinstance(a, str):
            raise PawnError("effect(\"tint\", color, amount) needs a color like \"#ff0000\" first.")
        amount = 0.4 if b is None else b
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise PawnError("The tint amount must be a number from 0 to 1.")
        amount = max(0.0, min(1.0, float(amount)))
        if amount <= 0:
            effects.pop("tint", None)
        else:
            effects["tint"] = (a, amount)
        return
    if isinstance(a, bool) or not isinstance(a, (int, float)):
        raise PawnError(f"effect(\"{name}\", amount) needs a number: {NUMERIC[name][1]}.")
    v = max(0.0, min(NUMERIC[name][0], float(a)))
    if v <= 0:
        effects.pop(name, None)
    else:
        effects[name] = v


def apply_cpu(img, effects, t=0.0):
    """A simpler version for when the graphics card path isn't available. Returns a new QImage."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QRadialGradient
    out = QImage(img)
    w, h = out.width(), out.height()
    pix = effects.get("pixelate", 0.0) * w / 960.0
    if pix > 1:
        small = out.scaled(max(1, int(w / pix)), max(1, int(h / pix)), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        out = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    blur = effects.get("blur", 0.0) * w / 960.0
    if blur > 0.5:
        small = out.scaled(max(1, int(w / (1 + blur))), max(1, int(h / (1 + blur))), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        out = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if effects.get("grayscale", 0.0) > 0:
        gray = out.convertToFormat(QImage.Format_Grayscale8).convertToFormat(QImage.Format_ARGB32_Premultiplied)
        p = QPainter(out)
        p.setOpacity(min(1.0, effects["grayscale"]))
        p.drawImage(0, 0, gray)
        p.end()
    if effects.get("invert", 0.0) >= 0.5:
        out.invertPixels()
    p = QPainter(out)
    if "tint" in effects:
        c = QColor(effects["tint"][0])
        c.setAlphaF(effects["tint"][1])
        p.fillRect(0, 0, w, h, c)
    v = effects.get("vignette", 0.0)
    if v > 0:
        g = QRadialGradient(w / 2, h / 2, max(w, h) * 0.7)
        g.setColorAt(0.45, QColor(0, 0, 0, 0))
        g.setColorAt(1.0, QColor(0, 0, 0, int(255 * min(1.0, v))))
        p.fillRect(QRectF(0, 0, w, h), g)
    sc = effects.get("scanlines", 0.0)
    if sc > 0:
        c = QColor(0, 0, 0, int(110 * sc))
        for y in range(0, h, 2):
            p.fillRect(0, y, w, 1, c)
    p.end()
    return out
