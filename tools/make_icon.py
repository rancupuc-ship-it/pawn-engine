"""Draws the Pawn Engine app icon (a golden chess pawn on a dark rounded square)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "assets"
S = 1024


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # background: dark charcoal rounded square with a soft vertical gradient
    bg = Image.new("RGBA", (S, S))
    px = bg.load()
    top, bot = (38, 43, 56), (17, 19, 25)
    for y in range(S):
        c = lerp(top, bot, y / S)
        for x in range(S):
            px[x, y] = (*c, 255)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), radius=230, fill=255)
    img.paste(bg, (0, 0), mask)

    # pawn silhouette on its own layer, gold gradient
    pawn = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(pawn)
    cx = S // 2
    d.ellipse((cx - 118, 168, cx + 118, 404), fill=255)                     # head
    d.rounded_rectangle((cx - 170, 392, cx + 170, 452), radius=30, fill=255)  # collar
    body = [(cx - 96, 440), (cx + 96, 440), (cx + 150, 700), (cx - 150, 700)]
    d.polygon(body, fill=255)                                                 # body
    d.ellipse((cx - 190, 640, cx + 190, 740), fill=255)                       # flare
    d.rounded_rectangle((cx - 250, 700, cx + 250, 800), radius=44, fill=255)  # base
    d.rounded_rectangle((cx - 290, 780, cx + 290, 860), radius=40, fill=255)  # plinth
    pawn = pawn.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: 255 if v > 127 else 0)

    grad = Image.new("RGBA", (S, S))
    gp = grad.load()
    c1, c2 = (255, 224, 140), (232, 160, 40)
    for y in range(S):
        c = lerp(c1, c2, max(0, min(1, (y - 160) / 700)))
        for x in range(S):
            gp[x, y] = (*c, 255)
    # soft shadow under the pawn
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sm = pawn.filter(ImageFilter.GaussianBlur(22))
    shadow.paste((0, 0, 0, 120), (0, 22), sm)
    img = Image.alpha_composite(img, shadow)
    img.paste(grad, (0, 0), pawn)

    # highlight on the head
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse((cx - 78, 208, cx - 6, 280), fill=(255, 250, 225, 150))
    hl = hl.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, hl)
    # thin gold rim on the tile
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle((24, 24, S - 24, S - 24), radius=230, outline=(242, 184, 75, 120), width=6)
    return Image.alpha_composite(img, rim)


def main():
    OUT.mkdir(exist_ok=True)
    big = build()
    big.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", sizes=[(s, s) for s in sizes])
    print("wrote", OUT / "icon.png", OUT / "icon.ico")


if __name__ == "__main__":
    main()
