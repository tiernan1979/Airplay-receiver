"""
Main application window — frameless QWidget, QPainter-based rendering.
"""
from __future__ import annotations

import gc
import math
import threading
from typing import TYPE_CHECKING

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from PySide6.QtCore import Qt, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QPixmap, QImage,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QSizePolicy, QApplication,
)

from airplay_receiver.platform import (
    IS_WINDOWS, set_window_no_taskbar, set_window_alpha,
)
from airplay_receiver.ui.buttons   import SphereButton, SmallCircleButton
from airplay_receiver.ui.colours   import rgb as _rgb, blend as _blend
from airplay_receiver.ui.settings  import SettingsDialog
from airplay_receiver.ui.widgets   import VolumeSlider, MarqueeLabel

if TYPE_CHECKING:
    from airplay_receiver.audio   import AudioEngine
    from airplay_receiver.config  import Config, PlayerState
    from airplay_receiver.dacp    import DacpRemote
    from airplay_receiver.themes  import ThemeManager


def pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    """Convert a PIL RGBA Image to a QPixmap efficiently."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class ModernUI(QWidget):
    W   = 370
    H   = 530
    TH  = 36    # titlebar height
    ART = 176   # artwork circle diameter

    def __init__(
        self,
        config: "Config",
        state:  "PlayerState",
        audio:  "AudioEngine",
        dacp:   "DacpRemote",
        theme:  "ThemeManager",
    ) -> None:
        super().__init__()
        import logging
        self._log    = logging.getLogger("AirPlay")
        self._config = config
        self._state  = state
        self._audio  = audio
        self._dacp   = dacp
        self._theme  = theme
        self._pulse  = 0.0
        self._bg_art = None
        self._last_art = None
        self._bg_pixmap: QPixmap | None = None
        self._art_pixmap: QPixmap | None = None
        self._tick_count = 0
        self._title_str  = ""
        self._drag_pos   = None

        self.setWindowTitle("AirPlay Receiver")
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self._setup_window()

        T = theme
        # Titlebar
        self._build_titlebar(T)

        # Status labels
        self._status_dot = QLabel("●", self)
        self._status_dot.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._status_dot.setFont(QFont("Segoe UI", 9))
        self._status_dot.move(17, self.TH + 10)

        self._status_txt = QLabel("STANDBY", self)
        self._status_txt.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._status_txt.setFont(QFont("Courier New", 7, QFont.Bold))
        self._status_txt.move(32, self.TH + 8)

        self._codec_lbl = QLabel("", self)
        self._codec_lbl.setStyleSheet(f"color: {T['teal']}; background: transparent;")
        self._codec_lbl.setFont(QFont("Courier New", 7, QFont.Bold))
        self._codec_lbl.move(self.W - 10, self.TH + 8)

        # Info label (artist · album)
        self._info_lbl = QLabel("", self)
        self._info_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._info_lbl.setFont(QFont("Segoe UI", 9))
        self._info_lbl.setAlignment(Qt.AlignCenter)
        self._info_lbl.setWordWrap(True)

        # Marquee title
        self._marquee = MarqueeLabel(
            self,
            fg=T["text"],
            bg=T["bg"],
        )

        # Volume slider
        self._vol_slider = VolumeSlider(
            self,
            initial=self._state.volume,
            theme=dict(theme._t),
        )
        self._vol_slider.valueChanged.connect(self._on_vol)

        # Transport buttons
        self._btn_prev = SmallCircleButton(T["card2"], T["accent"], self)
        self._btn_prev.clicked_signal.connect(lambda: self._dacp.prev_track())

        self._btn_play = SphereButton(T["accent"], T["accent2"], self)
        self._btn_play.clicked_signal.connect(self._play_pause)

        self._btn_next = SmallCircleButton(T["card2"], T["accent"], self)
        self._btn_next.clicked_signal.connect(lambda: self._dacp.next_track())

        # Bottom bar
        self._dev_lbl = QLabel(self)
        self._dev_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._dev_lbl.setFont(QFont("Courier New", 7))

        self._gear_btn = QPushButton("⚙", self)
        self._gear_btn.setFixedSize(28, 24)
        self._gear_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 11pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ color: {T['text']}; }}
        """)
        self._gear_btn.clicked.connect(self._open_settings)

        # Position everything
        self._layout_ui(T)

        # Wire state refresh
        state.on_change(lambda: None)   # _tick polls dirty flag
        self._refresh()

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    # ── Window setup ──────────────────────────────────────────────────────────
    def _setup_window(self) -> None:
        set_window_no_taskbar(self)
        set_window_alpha(self, 0.97)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move((sg.width() - self.W) // 2, (sg.height() - self.H) // 2)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _layout_ui(self, T: dict) -> None:
        W, H = self.W, self.H
        y = self.TH

        # Status row
        y += 8
        self._status_dot.move(17, y + 2)
        self._status_txt.move(32, y)
        self._codec_lbl.move(W - 10, y)
        y += 20

        # Artwork area
        sz = self.ART
        ax = (W - sz) // 2
        ay = y
        self._art_ax = ax
        self._art_ay = ay
        self._art_sz = sz
        y += sz + 10

        # Title
        self._marquee.setGeometry(16, y + 3, W - 32, 30)
        y += 30

        # Info label
        self._info_lbl.setGeometry(16, y, W - 32, 18)
        y += 22

        # Panel area
        self._panel_y = y
        y += 14

        # Volume slider
        vol_y = y
        self._vol_slider.setGeometry(52, vol_y, W - 104, self._vol_slider.height())
        self._vol_lbl = QLabel("VOL", self)
        self._vol_lbl.setStyleSheet(f"color: {T['teal']}; background: transparent;")
        self._vol_lbl.setFont(QFont("Courier New", 7, QFont.Bold))
        self._vol_lbl.move(20, vol_y + 8)
        self._vol_pct = QLabel(f"{self._state.volume}%", self)
        self._vol_pct.setStyleSheet(f"color: {T['text2']}; background: transparent;")
        self._vol_pct.setFont(QFont("Courier New", 9))
        self._vol_pct.move(W - 6, vol_y + 8)
        y += 28

        # Transport buttons
        self._btn_y = y
        sm_t = 44 + 16
        pl_t = 64 + 20
        gap = 8
        bx = (W - (sm_t + gap + pl_t + gap + sm_t)) // 2
        self._btn_prev.move(bx, y + 10)
        self._btn_play.move(bx + sm_t + gap, y)
        self._btn_next.move(bx + sm_t + gap + pl_t + gap, y + 10)
        y += 84

        # Bottom bar
        self._dev_lbl.move(12, y + 12)
        self._gear_btn.move(W - 36, y + 8)
        y += 34

        actual_h = y
        if actual_h != H:
            self.H = actual_h
            self.setFixedSize(W, actual_h)

    # ── Background ────────────────────────────────────────────────────────────
    def _render_bg_pixmap(self, artwork) -> QPixmap:
        """Render background (blurred art or gradient glow) to a QPixmap."""
        W, H = self.W, self.H
        panel_y = self._panel_y or int(H * 0.61)
        T = self._theme

        if not PIL_AVAILABLE:
            pix = QPixmap(W, H)
            pix.fill(QColor(T["bg"]))
            return pix

        if artwork:
            try:
                src = getattr(artwork, "im", artwork)
                bg  = src.convert("RGB").resize((W // 2, H // 2), Image.BILINEAR)
                bg  = bg.filter(ImageFilter.GaussianBlur(13))
                bg  = ImageEnhance.Brightness(bg).enhance(0.28)
                bg  = ImageEnhance.Color(bg).enhance(0.6)
                bg  = bg.resize((W, H), Image.BILINEAR)
            except Exception:
                artwork = None

        if not artwork:
            bg   = Image.new("RGB", (W, H), _rgb(T["bg"]))
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(glow)
            rv, gv, bv = _rgb(T["accent"])
            for r in range(120, 0, -6):
                t = r / 120
                a = int(18 * (1 - t) * t * 4)
                gd.ellipse([-20, -10, r * 2 - 20, r * 2 - 10],
                           fill=(rv, gv, bv, a))
            rv2, gv2, bv2 = _rgb(T["accent2"])
            for r in range(100, 0, -6):
                t = r / 100
                a = int(14 * (1 - t) * t * 4)
                gd.ellipse([W - r * 2 + 20, H - r * 2 + 10, W + 20, H + 10],
                           fill=(rv2, gv2, bv2, a))
            bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")

        # Panel
        panel = Image.new("RGB", (W, H - panel_y), _rgb(T["bg"]))
        bg.paste(panel, (0, panel_y))

        return pil_to_qpixmap(bg)

    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self, T: dict) -> None:
        self._tb_frame = QFrame(self)
        self._tb_frame.setGeometry(0, 0, self.W, self.TH)
        self._tb_frame.setStyleSheet(f"background: {T['tbarbg']};")
        self._tb_frame.setMouseTracking(True)

        self._tb_accent = QFrame(self._tb_frame)
        self._tb_accent.setFixedSize(3, self.TH)
        self._tb_accent.setStyleSheet(f"background: {T['accent']};")
        self._tb_accent.move(0, 0)

        self._tb_lbl = QLabel("  ♫  AIRPLAY RECEIVER", self._tb_frame)
        self._tb_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._tb_lbl.setFont(QFont("Courier New", 7, QFont.Bold))
        self._tb_lbl.move(8, 10)

        min_btn = QPushButton("  ─  ", self._tb_frame)
        min_btn.setFixedSize(36, self.TH)
        min_btn.move(self.W - 72, 0)
        min_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 10pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ background: {T['card2']}; color: {T['text']}; }}
        """)
        min_btn.clicked.connect(self._minimise)
        self._tb_min_btn = min_btn

        close_btn = QPushButton("  ✕  ", self._tb_frame)
        close_btn.setFixedSize(36, self.TH)
        close_btn.move(self.W - 36, 0)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 10pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ background: {T['accent2']}; color: white; }}
        """)
        close_btn.clicked.connect(self.quit_app)
        self._tb_close_btn = close_btn

    def mousePressEvent(self, event) -> None:
        if event.position().y() < self.TH:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def _minimise(self) -> None:
        self.hide()
        self._state.mark_dirty()

    # ── Artwork ───────────────────────────────────────────────────────────────
    def _render_art_pixmap(self, artwork) -> QPixmap | None:
        """Convert artwork PIL image to circular QPixmap."""
        if not PIL_AVAILABLE or not artwork:
            return None
        try:
            sz = self._art_sz
            src = getattr(artwork, "im", artwork)
            art = src.convert("RGBA").resize((sz, sz), Image.LANCZOS)

            mask = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, sz, sz], fill=255)
            art.putalpha(mask)

            return pil_to_qpixmap(art)
        except Exception:
            return None

    def _render_default_art(self) -> QPixmap:
        """Render default music note artwork as QPixmap."""
        sz = self._art_sz
        T = self._theme
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = sz // 2
        cx = cy = r

        for ri in range(r, 0, -1):
            v = int(12 * (1 - (ri / r) * 0.3))
            d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=(v, v, v, 255))

        tr, tg, tb = _rgb(T["teal"])
        bx1, by1 = cx - int(r * 0.30), cy - int(r * 0.30)
        for i in range(int(r * 0.9), 0, -2):
            t = i / (r * 0.9)
            a = int(130 * (1 - t) ** 1.0)
            d.ellipse([bx1 - i, by1 - i, bx1 + i, by1 + i], fill=(tr, tg, tb, a))

        ar, ag, ab = _rgb(T["accent"])
        bx2, by2 = cx + int(r * 0.22), cy + int(r * 0.22)
        for i in range(int(r * 0.7), 0, -2):
            t = i / (r * 0.7)
            a = int(80 * (1 - t) ** 1.2)
            d.ellipse([bx2 - i, by2 - i, bx2 + i, by2 + i], fill=(ar, ag, ab, a))

        mask = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, sz, sz], fill=255)
        img.putalpha(mask)

        note = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        nd = ImageDraw.Draw(note)
        mr, mg, mb = _rgb(T["text2"])
        nd.text((cx, cy), "♫", fill=(mr, mg, mb, 220), anchor="mm")
        note.putalpha(mask)
        img = Image.alpha_composite(img, note)

        return pil_to_qpixmap(img)

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Background
        if self._bg_pixmap:
            p.drawPixmap(0, 0, self._bg_pixmap)
        else:
            p.fillRect(self.rect(), QColor(self._theme["bg"]))

        # Artwork
        if self._art_pixmap:
            clip = QPainterPath()
            clip.addEllipse(QRectF(self._art_ax, self._art_ay, self._art_sz, self._art_sz))
            p.setClipPath(clip)
            p.drawPixmap(self._art_ax, self._art_ay, self._art_pixmap)
            p.setClipping(False)

        # Ring
        T = self._theme
        ring_pad = 12 + 5
        rx0 = self._art_ax - ring_pad
        ry0 = self._art_ay - ring_pad
        rx1 = self._art_ax + self._art_sz + ring_pad
        ry1 = self._art_ay + self._art_sz + ring_pad
        ring_w = self._art_sz + ring_pad * 2

        t = (math.sin(self._pulse) + 1) / 2
        if self._state.playing:
            col = _blend(T["accent"], T["teal"], t)
            dash = (5, 6) if t > 0.5 else (2, 10)
        else:
            col = T["border"]
            dash = (2, 14)

        p.setPen(QPen(QColor(col), 1, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(self._art_ax + self._art_sz / 2,
                              self._art_ay + self._art_sz / 2),
                      ring_w / 2, ring_w / 2)

        p.end()

    # ── Refresh ───────────────────────────────────────────────────────────────
    def _refresh(self) -> None:
        s = self._state
        T = self._theme

        title = s.title or ("Playing…" if s.playing else "")
        if title != self._title_str:
            self._title_str = title
            self._marquee.setText(title)

        parts = [p for p in [s.artist, s.album] if p]
        self._info_lbl.setText("  ·  ".join(parts))

        self._dev_lbl.setText(f"{self._config['device_name']}  ·  port {s.port}")

        self._codec_lbl.setText(s.codec or "")

        # Status
        if s.connected and s.playing:
            self._status_dot.setStyleSheet(f"color: {T['green']}; background: transparent;")
            self._status_txt.setText("PLAYING")
            self._status_txt.setStyleSheet(f"color: {T['green']}; background: transparent;")
        elif s.connected:
            self._status_dot.setStyleSheet(f"color: {T['amber']}; background: transparent;")
            self._status_txt.setText("CONNECTED")
            self._status_txt.setStyleSheet(f"color: {T['amber']}; background: transparent;")
        else:
            self._status_dot.setStyleSheet(f"color: {T['muted']}; background: transparent;")
            self._status_txt.setText("STANDBY")
            self._status_txt.setStyleSheet(f"color: {T['muted']}; background: transparent;")

        # Volume
        sv = s.volume
        if self._vol_slider.value() != sv:
            self._vol_slider.set_value(sv)
        self._vol_pct.setText(f"{sv}%")

        # Artwork
        if s.artwork and PIL_AVAILABLE:
            if s.artwork is not self._last_art:
                self._last_art = s.artwork
                try:
                    art_pix = self._render_art_pixmap(s.artwork)
                    if art_pix:
                        self._art_pixmap = art_pix
                except Exception as exc:
                    self._log.warning(f"render_art: {exc}")
                    self._art_pixmap = self._render_default_art()
                if s.artwork is not self._bg_art:
                    self._bg_art = s.artwork
                    try:
                        self._bg_pixmap = self._render_bg_pixmap(s.artwork)
                    except Exception as exc:
                        self._log.warning(f"render_bg: {exc}")
            self.update()
            return

        if self._last_art is not None:
            self._last_art = None
            self._art_pixmap = self._render_default_art()
        if self._bg_art is not None:
            self._bg_art = None
            self._bg_pixmap = self._render_bg_pixmap(None)
        self.update()

    # ── Button icon update ────────────────────────────────────────────────────
    def _update_play_button(self) -> None:
        T = self._theme
        accent = T["accent2"] if self._state.playing else T["accent"]
        self._btn_play.update_theme(accent, T["accent2"])

    # ── Tick (50ms animation + dirty-flag poll) ───────────────────────────────
    def _tick(self) -> None:
        if self._state.consume_dirty():
            self._refresh()

        self._tick_count += 1
        if self._tick_count >= 600:
            self._tick_count = 0
            gc.collect()

        self._pulse += 0.06
        self._update_play_button()
        self.update()

    # ── Volume ────────────────────────────────────────────────────────────────
    def _on_vol(self, val: int) -> None:
        self._audio._vol = max(0.0, min(1.0, val / 100.0))
        self._state.volume = val
        self._config["volume"] = val
        self._vol_pct.setText(f"{val}%")
        if hasattr(self, "_vol_timer") and self._vol_timer:
            try:
                self._vol_timer.stop()
            except Exception:
                pass
        from PySide6.QtCore import QTimer
        self._vol_timer = QTimer(self)
        self._vol_timer.setSingleShot(True)
        self._vol_timer.timeout.connect(
            lambda: self._dacp.set_volume(val) if self._state.active_remote else None
        )
        self._vol_timer.start(500)

    # ── Play/pause ────────────────────────────────────────────────────────────
    def _play_pause(self) -> None:
        if self._state.playing:
            self._audio.clear()
            self._state.playing = False
        else:
            self._state.playing = True
        self._state.mark_dirty()
        threading.Thread(target=self._dacp.play_pause, daemon=True).start()

    # ── Settings ──────────────────────────────────────────────────────────────
    def _open_settings(self) -> None:
        SettingsDialog(
            self, self._config, self._state,
            self._audio, self._theme, ui_ref=self,
        )

    # ── Retheme ───────────────────────────────────────────────────────────────
    def retheme(self) -> None:
        T = self._theme
        bg_col = QColor(T["bg"])
        self._tb_frame.setStyleSheet(f"background: {T['tbarbg']};")
        self._tb_accent.setStyleSheet(f"background: {T['accent']};")
        self._tb_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._tb_min_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 10pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ background: {T['card2']}; color: {T['text']}; }}
        """)
        self._tb_close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 10pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ background: {T['accent2']}; color: white; }}
        """)
        self._codec_lbl.setStyleSheet(f"color: {T['teal']}; background: transparent;")
        self._info_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._vol_lbl.setStyleSheet(f"color: {T['teal']}; background: transparent;")
        self._vol_pct.setStyleSheet(f"color: {T['text2']}; background: transparent;")
        self._dev_lbl.setStyleSheet(f"color: {T['muted']}; background: transparent;")
        self._gear_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']};
                font: 11pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ color: {T['text']}; }}
        """)
        self._vol_slider.update_theme(dict(T._t))
        self._marquee.update_theme(T["text"], T["bg"])
        self._btn_prev.update_theme(T["card2"], T["accent"])
        self._btn_next.update_theme(T["card2"], T["accent"])
        self._update_play_button()
        self._bg_pixmap = self._render_bg_pixmap(self._bg_art)
        if not self._state.artwork:
            self._art_pixmap = self._render_default_art()
        self.update()

    # ── Window controls ───────────────────────────────────────────────────────
    def show(self) -> None:
        super().show()
        self.raise_()
        self.activateWindow()

    def hide(self) -> None:
        super().hide()

    def quit_app(self) -> None:
        self._timer.stop()
        QApplication.quit()
