"""
Generates all App Store and Play Store assets for Gist.
Run from any directory:  python store-assets/generate_assets.py
Requires: Pillow  (pip install Pillow)
"""

from __future__ import annotations
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── Brand colours ──────────────────────────────────────────────────────────────
BG        = (10, 11, 13)          # #0A0B0D  dark canvas
PURPLE    = (86, 69, 212)         # #5645D4  primary accent
PURPLE_LT = (124, 107, 240)       # #7C6BF0  light accent
WHITE     = (255, 255, 255)
GREY      = (160, 160, 175)

OUT = Path(__file__).parent


# ── Font helpers ───────────────────────────────────────────────────────────────
def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ── Core icon drawing routine ──────────────────────────────────────────────────
def _draw_gist_icon(
    img: Image.Image,
    *,
    bg: tuple[int, int, int] | None = PURPLE,
    alpha_bg: bool = False,
) -> None:
    """Draw the Gist icon onto *img* (in-place).

    bg=None / alpha_bg=True → transparent background (for adaptive foreground).
    """
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")

    # Background
    if alpha_bg:
        pass  # leave transparent
    elif bg is not None:
        draw.rectangle([0, 0, w, h], fill=bg + (255,))

    # "G" lettermark – Helvetica-style flat-cap G
    # We draw it as a bold rounded rectangle arc + crossbar using primitives.
    cx, cy = w / 2, h / 2
    r = w * 0.30          # radius of the circular arc
    stroke = w * 0.085    # stroke width

    # Arc bounding box (slightly above centre to leave room for crossbar)
    arc_box = [cx - r, cy - r, cx + r, cy + r]

    # Full circle first (white stroke), then mask out top-right quadrant to open the G
    draw.arc(arc_box, start=30, end=330, fill=WHITE + (255,), width=int(stroke))

    # Horizontal crossbar (right half of the G)
    bar_y   = cy + r * 0.08
    bar_x1  = cx - stroke * 0.4
    bar_x2  = cx + r - stroke * 0.1
    draw.rectangle(
        [bar_x1, bar_y - stroke * 0.45, bar_x2, bar_y + stroke * 0.45],
        fill=WHITE + (255,),
    )

    # Short vertical on the right end to cap the crossbar
    cap_x = bar_x2 - stroke * 0.5
    draw.rectangle(
        [cap_x, bar_y - stroke * 0.45, cap_x + stroke, cy + stroke * 0.1],
        fill=WHITE + (255,),
    )


# ── Icon variants ──────────────────────────────────────────────────────────────
def _label(path: Path) -> str:
    try:
        return str(path.relative_to(OUT.parent))
    except ValueError:
        return str(path)


def _make_icon(size: int, path: Path) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_gist_icon(img)
    img.save(path, "PNG")
    print(f"  {_label(path)}")


def _make_adaptive_foreground(size: int, path: Path) -> None:
    """Android adaptive icon foreground — transparent background, white G centred."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_gist_icon(img, bg=None, alpha_bg=True)
    img.save(path, "PNG")
    print(f"  {_label(path)}")


def _make_adaptive_background(size: int, path: Path) -> None:
    img = Image.new("RGBA", (size, size), PURPLE + (255,))
    img.save(path, "PNG")
    print(f"  {_label(path)}")


def _make_monochrome(size: int, path: Path) -> None:
    """Monochrome adaptive icon — white G on black (Android 13+)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    _draw_gist_icon(img, bg=(0, 0, 0))
    img.save(path, "PNG")
    print(f"  {_label(path)}")


# ── Feature graphic (Play Store) ───────────────────────────────────────────────
def _make_feature_graphic(path: Path) -> None:
    W, H = 1024, 500
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    # Subtle purple gradient blob (top-left)
    for i in range(200, 0, -2):
        alpha = int(80 * (i / 200) ** 2)
        draw.ellipse(
            [W * 0.1 - i, H * 0.15 - i, W * 0.1 + i, H * 0.15 + i],
            fill=PURPLE + (alpha,),
        )

    # App icon (left side)
    icon_size = 160
    icon_x, icon_y = 90, (H - icon_size) // 2
    icon_img = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
    _draw_gist_icon(icon_img)
    # Rounded corners via mask
    mask = Image.new("L", (icon_size, icon_size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, icon_size, icon_size], radius=36, fill=255)
    img.paste(icon_img, (icon_x, icon_y), mask)

    # Text block
    tx = icon_x + icon_size + 40
    ty = H // 2 - 50

    fn_big  = _font(72, bold=True)
    fn_sub  = _font(32, bold=False)
    fn_tag  = _font(26, bold=False)

    draw.text((tx, ty), "Gist", font=fn_big, fill=WHITE)
    draw.text((tx, ty + 84), "Talk to your documents.", font=fn_sub, fill=GREY)
    draw.text((tx, ty + 130), "Ask questions. Get answers. Instantly.", font=fn_tag, fill=GREY)

    img.save(path, "PNG")
    print(f"  {path.relative_to(OUT)}")


# ── Screenshot mockup ──────────────────────────────────────────────────────────
def _make_screenshot(w: int, h: int, title: str, body: str, path: Path) -> None:
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    # Top status bar placeholder
    draw.rectangle([0, 0, w, 60], fill=(20, 21, 25))

    # Header bar
    draw.rectangle([0, 60, w, 130], fill=(18, 19, 22))
    fn_head = _font(34, bold=True)
    draw.text((24, 82), "Gist", font=fn_head, fill=WHITE)

    # Central card
    card_m = 32
    card_t, card_b = 160, h - 240
    draw.rounded_rectangle(
        [card_m, card_t, w - card_m, card_b],
        radius=24,
        fill=(22, 23, 28),
    )

    fn_title = _font(36, bold=True)
    fn_body  = _font(28, bold=False)
    fn_small = _font(24, bold=False)

    draw.text((card_m + 28, card_t + 32), title, font=fn_title, fill=WHITE)
    # Word-wrap body text
    words = body.split()
    lines: list[str] = []
    current = ""
    for w_word in words:
        test = (current + " " + w_word).strip()
        bbox = draw.textbbox((0, 0), test, font=fn_body)
        if bbox[2] - bbox[0] > w - card_m * 2 - 56:
            if current:
                lines.append(current)
            current = w_word
        else:
            current = test
    if current:
        lines.append(current)
    for i, line in enumerate(lines[:8]):
        draw.text((card_m + 28, card_t + 100 + i * 44), line, font=fn_body, fill=GREY)

    # Bottom CTA bar
    bar_y = h - 200
    draw.rounded_rectangle(
        [card_m, bar_y, w - card_m, bar_y + 72],
        radius=18,
        fill=PURPLE,
    )
    fn_cta = _font(30, bold=True)
    cta_text = "Ask anything…"
    bbox = draw.textbbox((0, 0), cta_text, font=fn_cta)
    cta_x = (w - (bbox[2] - bbox[0])) // 2
    draw.text((cta_x, bar_y + 18), cta_text, font=fn_cta, fill=WHITE)

    # Tagline
    fn_tag = _font(24, bold=False)
    tagline = "Gist — Talk to your documents"
    tbbox = draw.textbbox((0, 0), tagline, font=fn_tag)
    draw.text(((w - (tbbox[2] - tbbox[0])) // 2, h - 100), tagline, font=fn_tag, fill=GREY)

    img.save(path, "PNG")
    print(f"  {path.relative_to(OUT)}")


# ── Splash icon ────────────────────────────────────────────────────────────────
def _make_splash(path: Path) -> None:
    _make_icon(512, path)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\nGenerating Gist store assets…\n")

    # ── Icons ──────────────────────────────────────────────────────────────────
    print("Icons:")
    _make_icon(1024, OUT / "ios" / "icon-1024x1024.png")
    _make_icon(512,  OUT / "android" / "icon-512x512.png")
    _make_adaptive_foreground(1024, OUT / "android" / "adaptive-foreground-1024x1024.png")
    _make_adaptive_background(1024, OUT / "android" / "adaptive-background-1024x1024.png")
    _make_monochrome(1024, OUT / "android" / "adaptive-monochrome-1024x1024.png")

    # ── Feature graphic ────────────────────────────────────────────────────────
    print("\nFeature graphic:")
    _make_feature_graphic(OUT / "android" / "feature-graphic-1024x500.png")

    # ── Splash icon (used by Expo splash screen) ───────────────────────────────
    print("\nSplash icon:")
    _make_splash(OUT / "splash-icon-512x512.png")

    # ── Mobile assets (overwrite Expo placeholders) ────────────────────────────
    mobile_assets = Path(__file__).parent.parent / "mobile" / "assets" / "images"
    if mobile_assets.exists():
        print("\nMobile assets:")
        _make_icon(1024, mobile_assets / "icon.png")
        _make_icon(512,  mobile_assets / "splash-icon.png")
        _make_adaptive_foreground(1024, mobile_assets / "android-icon-foreground.png")
        _make_adaptive_background(1024, mobile_assets / "android-icon-background.png")
        _make_monochrome(1024, mobile_assets / "android-icon-monochrome.png")
        _make_icon(32, mobile_assets / "favicon.png")

    # ── iOS screenshots ────────────────────────────────────────────────────────
    print("\nScreenshots (iOS):")
    ios_screens = [
        # (width, height, label)
        (1320, 2868, "iphone-6_9in"),    # iPhone 16 Pro Max 6.9"
        (1284, 2778, "iphone-6_5in"),    # iPhone 14 Plus 6.5"
        (1242, 2208, "iphone-5_5in"),    # iPhone 8 Plus 5.5"
        (2048, 2732, "ipad-12_9in"),     # iPad Pro 12.9"
    ]
    screens_content = [
        ("Chat with any document", "Upload a PDF, Word file, image, or spreadsheet and start a conversation. Gist reads it so you don't have to."),
        ("Get the gist instantly", "Ask specific questions and get precise, cited answers — no scrolling through pages."),
        ("Summaries & key points", "One tap generates a concise summary and bullet-point key takeaways for any document."),
        ("Search across everything", "Find the answer you need across all your uploaded documents at once."),
    ]
    for (sw, sh, label), (title, body) in zip(ios_screens, screens_content):
        _make_screenshot(sw, sh, title, body, OUT / "screenshots" / "ios" / f"{label}.png")

    # ── Android screenshots ────────────────────────────────────────────────────
    print("\nScreenshots (Android):")
    android_screens = [
        (1080, 1920, "phone-standard"),
        (1200, 1920, "phone-large"),
        (1600, 2560, "tablet-7in"),
        (2048, 2732, "tablet-10in"),
    ]
    for (sw, sh, label), (title, body) in zip(android_screens, screens_content):
        _make_screenshot(sw, sh, title, body, OUT / "screenshots" / "android" / f"{label}.png")

    print("\nDone. All assets written to store-assets/\n")


if __name__ == "__main__":
    main()
