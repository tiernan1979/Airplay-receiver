"""
Reusable custom tkinter canvas widgets.
"""
from __future__ import annotations

import math
import tkinter as tk
from typing import Callable

try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .colours import rgb as _rgb, blend as _blend


class CanvasSlider(tk.Canvas):
    """
    Volume slider: rounded track with teal→accent gradient fill,
    clean dot thumb with glow ring.
    """
    TRACK_H = 4
    THUMB_R = 10
    PAD_X   = 14

    def __init__(
        self,
        parent,
        var: tk.IntVar,
        cmd: Callable[[int], None],
        width: int = 200,
        theme: dict | None = None,
        **kw,
    ) -> None:
        height = self.THUMB_R * 2 + 8
        try:
            bg = parent.cget("bg")
        except Exception:
            bg = "#100c1e"
        super().__init__(parent, width=width, height=height,
                         bg=bg, highlightthickness=0, **kw)
        self._var   = var
        self._cmd   = cmd
        self._W     = width
        self._H     = height
        self._drag  = False
        self._theme = theme or {}
        self._img_ref: object = None
        var.trace_add("write", lambda *_: self.after(0, self._redraw))
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._redraw()

    def update_theme(self, theme: dict) -> None:
        self._theme = theme
        self._redraw()

    def _val_to_x(self, val: int) -> int:
        return self.PAD_X + int((self._W - self.PAD_X * 2) * val / 100)

    def _x_to_val(self, x: int) -> int:
        return max(0, min(100, round(
            (x - self.PAD_X) / (self._W - self.PAD_X * 2) * 100
        )))

    def _redraw(self) -> None:
        if not PIL_AVAILABLE:
            return
        val    = self._var.get()
        W, H   = self._W, self._H
        cy     = H // 2
        tx0    = self.PAD_X
        tx1    = W - self.PAD_X
        th     = self.TRACK_H // 2
        fill_x = self._val_to_x(val)

        t_col  = self._theme.get("teal",   "#14b8a6")
        a_col  = self._theme.get("accent", "#8b5cf6")
        c2_col = self._theme.get("card2",  "#261e4a")
        txt_col= self._theme.get("text",   "#f1f5f9")

        img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Empty track
        tr, tg, tb = _rgb(c2_col)
        draw.rounded_rectangle(
            [tx0, cy - th - 1, tx1, cy + th + 1],
            radius=th + 1, fill=(tr, tg, tb, 200),
        )

        # Filled track
        if fill_x > tx0:
            r1, g1, b1 = _rgb(t_col)
            r2, g2, b2 = _rgb(a_col)
            fw = fill_x - tx0
            for xi in range(fw):
                t = xi / max(fw - 1, 1)
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                draw.line([(tx0 + xi, cy - th), (tx0 + xi, cy + th)],
                          fill=(r, g, b, 255))
            er, eg, eb = _rgb(t_col)
            draw.ellipse([tx0 - th, cy - th, tx0 + th, cy + th],
                         fill=(er, eg, eb, 255))

        # Thumb dot
        cx    = fill_x
        tr2   = self.THUMB_R
        gr, gg, gb = _rgb(a_col)
        for gi in range(tr2 + 5, tr2 - 1, -1):
            t  = (gi - tr2 + 1) / 6
            a  = int(55 * (1 - t) ** 1.8)
            draw.ellipse([cx - gi, cy - gi, cx + gi, cy + gi],
                         outline=(gr, gg, gb, a))
        wr, wg, wb = _rgb(txt_col)
        draw.ellipse([cx - tr2, cy - tr2, cx + tr2, cy + tr2],
                     fill=(wr, wg, wb, 255))
        sx = cx - tr2 // 3
        sy = cy - tr2 // 3
        ss = max(2, tr2 // 4)
        draw.ellipse([sx - ss, sy - ss, sx + ss, sy + ss],
                     fill=(255, 255, 255, 200))

        photo = ImageTk.PhotoImage(img)
        self._img_ref = photo
        self.delete("all")
        self.create_image(0, 0, anchor="nw", image=photo)

    def _on_press(self, e: tk.Event) -> None:
        self._drag = True; self._update(e.x)

    def _on_drag(self, e: tk.Event) -> None:
        if self._drag: self._update(e.x)

    def _on_release(self, e: tk.Event) -> None:
        self._drag = False; self._update(e.x)

    def _update(self, x: int) -> None:
        val = self._x_to_val(x)
        self._var.set(val)
        self._cmd(val)
        self._redraw()


class Marquee(tk.Canvas):
    """Horizontally scrolling single-line text label."""

    SPEED       = 1.2   # pixels per tick
    TICK_MS     = 50    # ms per tick
    PAUSE_TICKS = 80    # pause at each end

    def __init__(
        self,
        parent,
        var: tk.StringVar,
        font: tuple,
        fg: str,
        width: int,
        height: int = 28,
        **kw,
    ) -> None:
        try:
            bg = parent.cget("bg")
        except Exception:
            bg = "#100c1e"
        super().__init__(parent, width=width, height=height,
                         bg=bg, highlightthickness=0, **kw)
        self._var     = var
        self._font    = font
        self._fg      = fg
        self._W       = width
        self._H       = height
        self._offset  = 0.0
        self._dir     = 1
        self._pause   = self.PAUSE_TICKS
        self._text_w  = 0
        self._after_id: str | None = None
        var.trace_add("write", lambda *_: self.after(0, self._reset))
        self._reset()

    def update_theme(self, fg: str, bg: str) -> None:
        self._fg = fg
        self.configure(bg=bg)
        self._reset()

    def _reset(self) -> None:
        if self._after_id:
            try: self.after_cancel(self._after_id)
            except Exception: pass
        self._offset = 0.0
        self._dir    = 1
        self._pause  = self.PAUSE_TICKS
        self._redraw()
        self._loop()

    def _measure(self, text: str) -> int:
        self.update_idletasks()
        tid = self.create_text(0, 0, text=text, font=self._font, anchor="nw")
        bb  = self.bbox(tid)
        self.delete(tid)
        return (bb[2] - bb[0]) if bb else 0

    def _redraw(self) -> None:
        self.delete("all")
        text = self._var.get()
        if not text:
            return
        self._text_w = self._measure(text)
        if self._text_w <= self._W:
            self.create_text(self._W // 2, self._H // 2, text=text,
                             font=self._font, fill=self._fg, anchor="center")
        else:
            x = self._W // 2 - self._offset
            self.create_text(x, self._H // 2, text=text,
                             font=self._font, fill=self._fg, anchor="center")
            bg = self.cget("bg")
            self.create_rectangle(0, 0, 18, self._H, fill=bg, outline="")
            self.create_rectangle(self._W - 18, 0, self._W, self._H,
                                  fill=bg, outline="")

    def _loop(self) -> None:
        overflow = self._text_w - self._W + 30
        if overflow > 0:
            if self._pause > 0:
                self._pause -= 1
            else:
                self._offset += self.SPEED * (-self._dir)
                if self._offset >= overflow:
                    self._offset = overflow; self._dir = -1
                    self._pause  = self.PAUSE_TICKS
                elif self._offset <= 0:
                    self._offset = 0; self._dir = 1
                    self._pause  = self.PAUSE_TICKS
            self._redraw()
        self._after_id = self.after(self.TICK_MS, self._loop)
