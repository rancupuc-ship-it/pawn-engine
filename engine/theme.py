"""UI theme: one set of colors, font and corner roundness shared by every button, bar, slider and so on."""

DEFAULT_THEME = {
    "accent": "#f2b84b",         # bar and slider fill, checkmarks, focused text box
    "button": "#3a4256",
    "button_hover": "#4a5570",
    "button_press": "#2a3042",
    "back": "#232838",           # tracks, text boxes
    "text": "#ffffff",
    "radius": 8,
    "font": "",                  # a font file such as assets/fonts/pixel.ttf, or empty for the default
}
THEME_LABELS = {
    "accent": "Accent", "button": "Button", "button_hover": "Button (mouse over)",
    "button_press": "Button (pressed)", "back": "Track / text box", "text": "Text",
}


def merged(theme):
    out = dict(DEFAULT_THEME)
    if isinstance(theme, dict):
        for k, v in theme.items():
            if k in out and type(v) is type(out[k]):
                out[k] = v
    return out


def resolve(o, field, theme):
    """The color to use for an object's color field: its own if set, otherwise from the theme."""
    own = getattr(o, field, "")
    if own:
        return own
    k = o.kind
    if field == "color":
        return theme["button"] if k == "button" else theme["accent"]
    if field == "back_color":
        return theme["back"]
    if field == "hover_color":
        return theme["button_hover"]
    if field == "press_color":
        return theme["button_press"]
    if field == "text_color":
        return theme["text"]
    return "#ffffff"


def corner(o, theme):
    return o.radius if o.radius is not None and o.radius >= 0 else theme["radius"]
