"""
Colour helper utilities shared across all UI modules.
"""
from __future__ import annotations

_NAMED: dict[str, tuple[int, int, int]] = {
    "white": (255, 255, 255), "black": (0, 0, 0),
    "red":   (255, 0,   0),   "green": (0, 255, 0),
    "blue":  (0,   0, 255),   "gray":  (128, 128, 128),
    "grey":  (128, 128, 128),
}


def rgb(c: str) -> tuple[int, int, int]:
    """Parse hex colour string or named colour to (r, g, b) tuple."""
    c = c.strip()
    if c in _NAMED:
        return _NAMED[c]
    c = c.lstrip("#")
    if len(c) == 3:
        c = c[0]*2 + c[1]*2 + c[2]*2
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def blend(c1: str, c2: str, t: float) -> str:
    """Linear interpolate between two hex colours. t=0 → c1, t=1 → c2."""
    r1, g1, b1 = rgb(c1)
    r2, g2, b2 = rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_of(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"
