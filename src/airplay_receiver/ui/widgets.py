"""
Qt custom widgets — volume slider and marquee text.

All rendering is done with QPainter for memory efficiency.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from airplay_receiver.ui.colours import rgb as _rgb, blend as _blend


class VolumeSlider(QWidget):
    """
    Volume slider: rounded track with teal→accent gradient fill,
    clean dot thumb with glow ring. Uses QPainter (no PIL).
    """

    TRACK_H = 4
    THUMB_R = 10
    PAD_X   = 14

    valueChanged = Signal(int)

    def __init__(
        self,
        parent=None,
        initial: int = 80,
        theme: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._val   = initial
        self._theme = theme or {}
        self._drag  = False
        h = self.THUMB_R * 2 + 8
        self.setFixedHeight(h)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def update_theme(self, theme: dict) -> None:
        self._theme = theme
        self.update()

    def set_value(self, val: int) -> None:
        self._val = max(0, min(100, val))
        self.update()

    def value(self) -> int:
        return self._val

    def _val_to_x(self, val: int) -> float:
        w = self.width()
        return self.PAD_X + (w - self.PAD_X * 2) * val / 100.0

    def _x_to_val(self, x: float) -> int:
        w = self.width()
        return max(0, min(100, round(
            (x - self.PAD_X) / max(w - self.PAD_X * 2, 1) * 100
        )))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        H = self.height()
        cy = H // 2
        tx0 = self.PAD_X
        tx1 = W - self.PAD_X
        th = self.TRACK_H // 2
        fill_x = self._val_to_x(self._val)

        t_col  = self._theme.get("teal",   "#14b8a6")
        a_col  = self._theme.get("accent", "#8b5cf6")
        c2_col = self._theme.get("card2",  "#261e4a")
        txt_col= self._theme.get("text",   "#f1f5f9")

        track_col  = QColor(c2_col)
        teal_col   = QColor(t_col)
        accent_col = QColor(a_col)
        white_col  = QColor(txt_col)

        # Empty track
        track_rect = QRectF(tx0, cy - th - 1, tx1 - tx0, (th + 1) * 2)
        p.setBrush(track_col)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(track_rect, th + 1, th + 1)

        # Filled track — gradient
        if fill_x > tx0:
            fill_rect = QRectF(tx0, cy - th, fill_x - tx0, th * 2)
            for xi in range(int(fill_x - tx0)):
                t = xi / max(fill_x - tx0 - 1, 1)
                r = int(teal_col.red()   + (accent_col.red()   - teal_col.red())   * t)
                g = int(teal_col.green() + (accent_col.green() - teal_col.green()) * t)
                b = int(teal_col.blue()  + (accent_col.blue()  - teal_col.blue())  * t)
                p.setPen(QColor(r, g, b))
                p.drawLine(int(tx0 + xi), cy - th, int(tx0 + xi), cy + th)

            # Left end cap
            p.setBrush(teal_col)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(tx0, cy), th, th)

        # Thumb dot
        cx = fill_x
        tr2 = self.THUMB_R

        # Glow ring
        for gi in range(tr2 + 5, tr2 - 1, -1):
            t = (gi - tr2 + 1) / 6.0
            a = int(55 * (1 - t) ** 1.8)
            glow_c = QColor(accent_col.red(), accent_col.green(), accent_col.blue(), a)
            p.setPen(QPen(glow_c, 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), gi, gi)

        # White thumb
        p.setBrush(white_col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), tr2, tr2)

        # Small highlight on thumb
        sx = cx - tr2 // 3
        sy = cy - tr2 // 3
        ss = max(2, tr2 // 4)
        p.setBrush(QColor(255, 255, 255, 200))
        p.drawEllipse(QPointF(sx, sy), ss, ss)

        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag = True
            self._update_from_pos(event.position().x())

    def mouseMoveEvent(self, event) -> None:
        if self._drag:
            self._update_from_pos(event.position().x())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drag:
            self._drag = False
            self._update_from_pos(event.position().x())

    def _update_from_pos(self, x: float) -> None:
        val = self._x_to_val(x)
        if val != self._val:
            self._val = val
            self.valueChanged.emit(val)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()


class MarqueeLabel(QWidget):
    """Horizontally scrolling single-line text label."""

    SPEED       = 1.2
    TICK_MS     = 50
    PAUSE_TICKS = 80

    def __init__(
        self,
        parent=None,
        font: QFont | None = None,
        fg: str = "#f1f5f9",
        bg: str = "#100c1e",
    ) -> None:
        super().__init__(parent)
        self._text    = ""
        self._fg      = QColor(fg)
        self._bg      = QColor(bg)
        self._font    = font or QFont("Segoe UI", 12)
        self._font.setBold(True)
        self._offset  = 0.0
        self._dir     = 1
        self._pause   = self.PAUSE_TICKS
        self._text_w  = 0
        self._timer   = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.TICK_MS)

    def setText(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._reset()

    def text(self) -> str:
        return self._text

    def update_theme(self, fg: str, bg: str) -> None:
        self._fg = QColor(fg)
        self._bg = QColor(bg)
        self._reset()

    def _reset(self) -> None:
        self._offset = 0.0
        self._dir    = 1
        self._pause  = self.PAUSE_TICKS
        self._measure_text()
        self.update()

    def _measure_text(self) -> None:
        fm = QFontMetrics(self._font)
        self._text_w = fm.horizontalAdvance(self._text) if self._text else 0

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self._font)

        W = self.width()
        H = self.height()
        p.fillRect(self.rect(), self._bg)

        if not self._text:
            return

        if self._text_w <= W:
            p.setPen(self._fg)
            p.drawText(self.rect(), Qt.AlignCenter, self._text)
        else:
            x = W // 2 - self._offset
            p.setPen(self._fg)
            p.drawText(int(x), 0, self._text_w, H,
                       Qt.AlignVCenter | Qt.AlignLeft, self._text)

            # Fade edges
            fade_w = 18
            fade_l = QRectF(0, 0, fade_w, H)
            fade_r = QRectF(W - fade_w, 0, fade_w, H)
            p.fillRect(fade_l, self._bg)
            p.fillRect(fade_r, self._bg)

        p.end()

    def _tick(self) -> None:
        overflow = self._text_w - self.width() + 30
        if overflow > 0:
            if self._pause > 0:
                self._pause -= 1
            else:
                self._offset += self.SPEED * (-self._dir)
                if self._offset >= overflow:
                    self._offset = overflow
                    self._dir = -1
                    self._pause = self.PAUSE_TICKS
                elif self._offset <= 0:
                    self._offset = 0
                    self._dir = 1
                    self._pause = self.PAUSE_TICKS
            self.update()
