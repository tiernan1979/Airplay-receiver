"""
Qt custom button widgets — glossy sphere and flat circle buttons.

Rendered with QPainter (no PIL dependency) for better memory efficiency.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QPainterPath, QRadialGradient, QColor, QPen, QBrush,
)
from PySide6.QtWidgets import QAbstractButton


class SphereButton(QAbstractButton):
    """Glossy sphere button — used for the play/pause transport button."""

    SPHERE_SIZE = 64
    PAD = 12

    clicked_signal = Signal()

    def __init__(
        self,
        accent: str,
        accent2: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._accent  = QColor(accent)
        self._accent2 = QColor(accent2)
        self._hover   = False
        self.setFixedSize(self.SPHERE_SIZE + self.PAD * 2,
                          self.SPHERE_SIZE + self.PAD * 2)
        self.setCursor(Qt.PointingHandCursor)

    def _accent_color(self) -> QColor:
        return self._accent2 if self._hover else self._accent

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        r = self.SPHERE_SIZE / 2.0

        accent_col = self._accent_color()

        # Outer glow ring
        glow_pen = QPen(accent_col, 2)
        glow_pen.setStyle(Qt.DashLine)
        p.setPen(glow_pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r + 8, r + 8)

        # Dark base
        base_grad = QRadialGradient(cx, cy, r)
        base_grad.setColorAt(0.0, QColor(20, 20, 30))
        base_grad.setColorAt(1.0, QColor(6, 6, 10))
        p.setBrush(base_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Primary colour blob — upper-left
        blob1 = QRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 0.75)
        c = accent_col
        blob1.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 110))
        blob1.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        p.setBrush(blob1)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Secondary lighter blob — lower-right
        lr = min(255, c.red() * 2 + 60)
        lg = min(255, c.green() * 2 + 50)
        lb = min(255, c.blue() * 2 + 60)
        blob2 = QRadialGradient(cx + r * 0.22, cy + r * 0.22, r * 0.6)
        blob2.setColorAt(0.0, QColor(lr, lg, lb, 55))
        blob2.setColorAt(1.0, QColor(lr, lg, lb, 0))
        p.setBrush(blob2)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Clip path for highlights
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), r, r)

        # White highlight A — large soft bloom top-left
        h1 = QRadialGradient(cx - r * 0.36, cy - r * 0.40, r * 0.55)
        h1.setColorAt(0.0, QColor(255, 255, 255, 190))
        h1.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(h1)
        p.setClipPath(clip)
        p.drawEllipse(QPointF(cx - r * 0.36, cy - r * 0.40), r * 0.55, r * 0.34)

        # White highlight B — smaller secondary
        h2 = QRadialGradient(cx + r * 0.26, cy - r * 0.05, r * 0.18)
        h2.setColorAt(0.0, QColor(255, 255, 255, 90))
        h2.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(h2)
        p.drawEllipse(QPointF(cx + r * 0.26, cy - r * 0.05), r * 0.18, r * 0.12)

        # White highlight C — diffuse centre reflection
        h3 = QRadialGradient(cx - r * 0.06, cy - r * 0.18, r * 0.22)
        h3.setColorAt(0.0, QColor(255, 255, 255, 45))
        h3.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(h3)
        p.setClipPath(clip)
        p.drawEllipse(QPointF(cx - r * 0.06, cy - r * 0.18), r * 0.22, r * 0.22)

        p.setClipping(False)

        # Pressed dark overlay
        if self.isDown():
            p.setBrush(QColor(0, 0, 0, 80))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # Bottom shadow
        shadow = QRadialGradient(cx, cy + r * 0.3, r * 0.7)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 60))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow)
        p.setClipPath(clip)
        p.drawEllipse(QPointF(cx, cy + r * 0.3), r * 0.7, r * 0.25)

        p.end()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.update()
        if self.rect().contains(event.pos()):
            self.clicked_signal.emit()

    def update_theme(self, accent: str, accent2: str) -> None:
        self._accent  = QColor(accent)
        self._accent2 = QColor(accent2)
        self.update()


class SmallCircleButton(QAbstractButton):
    """Flat circle button — used for prev/next transport buttons."""

    CIRCLE_SIZE = 44
    PAD = 10

    clicked_signal = Signal()

    def __init__(
        self,
        card2: str,
        accent: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._card2_col = QColor(card2)
        self._accent_col = QColor(accent)
        self._hover = False
        self.setFixedSize(self.CIRCLE_SIZE + self.PAD * 2,
                          self.CIRCLE_SIZE + self.PAD * 2)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        r = self.CIRCLE_SIZE / 2.0

        # Hover glow ring
        if self._hover:
            glow_pen = QPen(self._accent_col, 2)
            p.setPen(glow_pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r + 5, r + 5)

        # Circle fill
        cr, cg, cb = self._card2_col.red(), self._card2_col.green(), self._card2_col.blue()
        if self._hover:
            cr, cg, cb = min(255, cr + 45), min(255, cg + 45), min(255, cb + 45)
        if self.isDown():
            cr, cg, cb = max(0, cr - 30), max(0, cg - 30), max(0, cb - 30)
        p.setBrush(QColor(cr, cg, cb, 220))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        p.end()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.update()
        if self.rect().contains(event.pos()):
            self.clicked_signal.emit()

    def update_theme(self, card2: str, accent: str) -> None:
        self._card2_col = QColor(card2)
        self._accent_col = QColor(accent)
        self.update()
