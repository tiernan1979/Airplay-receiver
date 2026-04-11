"""
PIL-rendered sphere button images.
Cached by (size, color, glow, pressed) to avoid re-rendering on hover.
"""
from __future__ import annotations

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from airplay_receiver.ui.colours import rgb as _rgb

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {}
_CACHE_MAX   = 12


def _evict() -> None:
    if len(_cache) >= _CACHE_MAX:
        del _cache[next(iter(_cache))]


def clear_cache() -> None:
    _cache.clear()


# ── Sphere renderer ────────────────────────────────────────────────────────────
def make_sphere(size: int, color: str, glow: str, pressed: bool = False) -> "Image.Image | None":
    """
    Render a dark glossy sphere button image.
    Uses the CSS radial-gradient technique from smart-home UIs:
      - Near-black radial base
      - Two low-opacity colour blobs at strategic positions
      - Three blurred white highlight layers for gloss
    Rendered at 1.5× and Lanczos-downscaled for anti-aliasing.
    Cached — same args return the cached image instantly.
    """
    if not PIL_AVAILABLE:
        return None
    key = (size, color, glow, pressed)
    if key in _cache:
        return _cache[key]

    pad   = 10
    total = size + pad * 2
    # 1.5× supersampling
    S2  = size  * 3 // 2
    P2  = pad   * 3 // 2
    T2  = total * 3 // 2

    base = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    cx = cy = P2 + S2 // 2
    r  = S2 // 2
    br, bg_, bb = _rgb(color)
    gr, gg, gb  = _rgb(glow)

    # 1. Near-black radial base
    for i in range(r, 0, -2):
        t = i / r
        v = int(6 + 8 * (1 - t))
        draw.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(v, v, v, 255))

    # 2. Primary colour blob — upper-left
    bx1 = cx - int(r * 0.38); by1 = cy - int(r * 0.38)
    for i in range(int(r * 0.80), 0, -3):
        t = i / (r * 0.80); a = int(110 * (1 - t) ** 0.85)
        draw.ellipse([bx1-i, by1-i, bx1+i, by1+i], fill=(br, bg_, bb, a))

    # 3. Secondary lighter blob — lower-right
    lr = min(255, int(br * 0.6 + 60))
    lg = min(255, int(bg_ * 0.6 + 50))
    lb = min(255, int(bb * 0.6 + 60))
    bx2 = cx + int(r * 0.22); by2 = cy + int(r * 0.22)
    for i in range(int(r * 0.65), 0, -3):
        t = i / (r * 0.65); a = int(55 * (1 - t) ** 1.0)
        draw.ellipse([bx2-i, by2-i, bx2+i, by2+i], fill=(lr, lg, lb, a))

    # 4. Bottom shadow
    shadow = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i in range(int(r * 0.7), 0, -3):
        t = i / (r * 0.7); a = int(160 * (1 - t) ** 0.6)
        sy = cy + int(r * 0.45)
        sd.ellipse([cx-i, sy - i//3, cx+i, sy + i//3], fill=(0, 0, 0, a))
    base = Image.alpha_composite(base, shadow)

    # 5. Clip to circle
    mask = Image.new("L", (T2, T2), 0)
    ImageDraw.Draw(mask).ellipse([P2, P2, P2+S2, P2+S2], fill=255)
    base.putalpha(mask)

    # 6. White highlight A — large soft bloom top-left
    hl_a  = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    ha    = ImageDraw.Draw(hl_a)
    h1x   = cx - int(r * 0.36); h1y = cy - int(r * 0.40)
    hw    = int(r * 0.58);       hh  = int(r * 0.34)
    mhwh  = max(hw, hh)
    for i in range(mhwh, 0, -3):
        t = i / mhwh; a = int(190 * (1 - t) ** 1.5)
        ha.ellipse([h1x - i*hw//mhwh, h1y - i*hh//mhwh,
                    h1x + i*hw//mhwh, h1y + i*hh//mhwh], fill=(255, 255, 255, a))
    hl_a = hl_a.filter(ImageFilter.GaussianBlur(radius=4))
    hl_a.putalpha(mask)
    base = Image.alpha_composite(base, hl_a)

    # 7. White highlight B — smaller secondary
    hl_b = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    hb   = ImageDraw.Draw(hl_b)
    h2x  = cx + int(r * 0.26); h2y = cy - int(r * 0.05)
    h2r  = int(r * 0.18)
    for i in range(h2r, 0, -2):
        t = i / h2r; a = int(90 * (1 - t) ** 1.6)
        hb.ellipse([h2x-i, h2y-i//2, h2x+i, h2y+i//2], fill=(255, 255, 255, a))
    hl_b = hl_b.filter(ImageFilter.GaussianBlur(radius=2))
    hl_b.putalpha(mask)
    base = Image.alpha_composite(base, hl_b)

    # 8. White highlight C — diffuse centre reflection
    hl_c = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    hc   = ImageDraw.Draw(hl_c)
    h3x  = cx - int(r * 0.06); h3y = cy - int(r * 0.18)
    h3r  = int(r * 0.22)
    for i in range(h3r, 0, -3):
        t = i / h3r; a = int(45 * (1 - t) ** 2.0)
        hc.ellipse([h3x-i, h3y-i, h3x+i, h3y+i], fill=(255, 255, 255, a))
    hl_c = hl_c.filter(ImageFilter.GaussianBlur(radius=6))
    hl_c.putalpha(mask)
    base = Image.alpha_composite(base, hl_c)

    # 9. Outer glow ring
    glow_l = Image.new("RGBA", (T2, T2), (0, 0, 0, 0))
    gd     = ImageDraw.Draw(glow_l)
    for gi in range(22, 0, -2):
        a = int(50 * (gi / 22) ** 2.0)
        gd.ellipse([P2-gi, P2-gi, P2+S2+gi, P2+S2+gi],
                   outline=(gr, gg, gb, a), width=1)
    base = Image.alpha_composite(glow_l, base)

    if pressed:
        dark = Image.new("RGBA", (T2, T2), (0, 0, 0, 65))
        base = Image.alpha_composite(base, dark)

    result = base.resize((total, total), Image.LANCZOS)
    _evict()
    _cache[key] = result
    return result


def make_small_circle(
    size: int, card2_color: str, accent_color: str,
    hover: bool = False, pressed: bool = False,
) -> "Image.Image | None":
    """Flat circle background for prev/next buttons."""
    if not PIL_AVAILABLE:
        return None
    pad   = 8
    total = size + pad * 2
    img   = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    d     = ImageDraw.Draw(img)
    cr, cg, cb = _rgb(card2_color)
    if hover:
        cr = min(255, cr + 45); cg = min(255, cg + 45); cb = min(255, cb + 45)
    if pressed:
        cr = max(0, cr - 30); cg = max(0, cg - 30); cb = max(0, cb - 30)
    d.ellipse([pad, pad, pad + size, pad + size], fill=(cr, cg, cb, 220))
    if hover:
        gr, gg, gb = _rgb(accent_color)
        for gi in range(5, 0, -1):
            a = int(28 * (gi / 5) ** 1.5)
            d.ellipse([pad-gi, pad-gi, pad+size+gi, pad+size+gi],
                      outline=(gr, gg, gb, a))
    return img
