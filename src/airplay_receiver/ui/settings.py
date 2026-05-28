"""
Settings dialog — frameless QDialog, themed to match main window style.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame, QWidget,
)

from airplay_receiver.platform import open_path, THEME_FILE, LOG_FILE

if TYPE_CHECKING:
    from airplay_receiver.config   import Config, PlayerState
    from airplay_receiver.audio    import AudioEngine
    from airplay_receiver.themes   import ThemeManager


def _theme_qss(T: dict) -> str:
    """Build Qt Style Sheet from theme dict."""
    bg   = T["bg"]
    card = T.get("input_bg", T["card"])
    fg   = T.get("input_fg", T["text"])
    accent = T["accent"]
    border = T["border"]
    card2 = T["card2"]
    return f"""
    QDialog {{ background: {bg}; }}
    QLabel {{ color: {fg}; background: transparent; }}
    QLineEdit {{
        background: {card}; color: {fg}; border: 1px solid {border};
        border-radius: 4px; padding: 8px 12px; font-size: 15pt;
        selection-background-color: {accent};
    }}
    QComboBox {{
        background: {card}; color: {fg}; border: 1px solid {border};
        border-radius: 4px; padding: 8px 12px; font-size: 15pt;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 32px;
        border-left: 1px solid {border};
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
        background: {card2};
    }}
    QComboBox QAbstractItemView {{
        background: {card}; color: {fg}; selection-background-color: {accent};
        border: 1px solid {border};
    }}
    QPushButton {{
        background: {card2}; color: {fg}; border: none;
        border-radius: 4px; padding: 10px 20px; font-size: 15pt;
    }}
    QPushButton:hover {{ background: {border}; }}
    QPushButton:pressed {{ background: {accent}; color: white; }}
    QCheckBox {{
        color: {T["muted"]}; spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {border}; border-radius: 3px;
        background: {card};
    }}
    QCheckBox::indicator:checked {{
        background: {accent}; border-color: {accent};
    }}
    QFrame[frameShape="4"] {{
        color: {border};
    }}
    """


class SettingsDialog(QDialog):
    """Frameless settings dialog. Opened from the ⚙ gear icon."""

    def __init__(
        self,
        parent,
        config: "Config",
        state:  "PlayerState",
        audio:  "AudioEngine",
        theme:  "ThemeManager",
        ui_ref=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._state  = state
        self._audio  = audio
        self._theme  = theme
        self._ui_ref = ui_ref
        self._drag_pos = None

        T = theme
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(480, 620)
        self.setStyleSheet(_theme_qss(T._t))

        if parent:
            px, py = parent.x(), parent.y()
            pw, ph = parent.width(), parent.height()
            self.move(px + (pw - 480) // 2, py + (ph - 620) // 2)

        self._build_titlebar(T)
        self._build_body(T)

    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self, T: dict) -> None:
        tb = QFrame(self)
        tb.setFixedHeight(40)
        tb.setStyleSheet(f"background: {T['tbarbg']};")
        tb.move(0, 0)
        tb.resize(480, 40)

        accent_bar = QFrame(tb)
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(f"background: {T['accent']};")
        accent_bar.move(0, 0)
        accent_bar.resize(3, 40)

        lbl = QLabel("  \u2699  SETTINGS", tb)
        lbl.setStyleSheet(
            f"color: {T['muted']}; font: 12pt 'Courier New'; font-weight: bold; background: transparent;"
        )
        lbl.move(10, 10)

        close_btn = QPushButton("  \u2715  ", tb)
        close_btn.setFixedSize(44, 40)
        close_btn.move(480 - 44, 0)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T['muted']}; font: 15pt 'Segoe UI'; border: none; }}
            QPushButton:hover {{ background: {T['accent2']}; color: white; }}
        """)
        close_btn.clicked.connect(self.close)

        tb.setMouseTracking(True)
        close_btn.raise_()

    def mousePressEvent(self, event) -> None:
        if event.position().y() < 40:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self, T: dict) -> None:
        container = QWidget(self)
        container.setGeometry(0, 40, 480, 620 - 40)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 14, 24, 20)
        layout.setSpacing(14)

        def section_header(text: str) -> None:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {T['teal']}; font: 12pt 'Courier New'; font-weight: bold;"
            )
            layout.addWidget(lbl)
            layout.addSpacing(6)

        # Device name
        section_header("DEVICE NAME  (restart required)")
        name_edit = QLineEdit(self._config["device_name"])
        layout.addWidget(name_edit)
        self._name_edit = name_edit

        # Theme
        section_header("THEME")
        names = self._theme.names()
        cur = self._config["theme"] if self._config["theme"] in names else "Indigo Night"
        theme_cb = QComboBox()
        theme_cb.addItems(names)
        theme_cb.setCurrentText(cur)
        layout.addWidget(theme_cb)
        self._theme_cb = theme_cb

        theme_path_lbl = QLabel(f"Custom themes: {THEME_FILE}")
        theme_path_lbl.setStyleSheet(f"color: {T['muted']}; font: 11pt 'Courier New';")
        layout.addWidget(theme_path_lbl)

        # Audio device
        section_header("AUDIO OUTPUT  (optical / S-PDIF)")
        devs = self._audio.list_devices()
        dn = ["Default (system)"] + [d[1] for d in devs]
        di = [None] + [d[0] for d in devs]
        cur_d = di.index(self._config["audio_device"]) if self._config["audio_device"] in di else 0

        audio_cb = QComboBox()
        audio_cb.addItems(dn)
        audio_cb.setCurrentIndex(cur_d)
        layout.addWidget(audio_cb)
        self._audio_cb = audio_cb
        self._audio_dn = dn
        self._audio_di = di

        # Audio status
        section_header("AUDIO STATUS")

        src = self._audio.SRC_RATE
        dst = self._audio._dst_rate
        resample_text = (
            f"\u2713  {src} Hz  (no resampling)" if src == dst
            else f"\u2195  {src} Hz \u2192 {dst} Hz  (resampling)"
        )
        resample_col = T["green"] if src == dst else T["amber"]
        alac_txt = "\u2713  PyAV \u2014 ALAC decoding active" if self._alac_ok() else "\u2717  pip install av  \u2014 REQUIRED"
        alac_col = T["green"] if self._alac_ok() else T["accent2"]

        for txt, col in [(resample_text, resample_col), (alac_txt, alac_col)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color: {col}; font: 12pt 'Courier New';")
            layout.addWidget(lbl)

        # Developer
        section_header("DEVELOPER")
        dbg_layout = QHBoxLayout()
        dbg_layout.setContentsMargins(0, 0, 0, 0)

        self._debug_on = bool(self._config.get("debug_mode", False))
        self._dbg_btn = QPushButton("DEBUG  ON" if self._debug_on else "DEBUG  OFF")
        self._dbg_btn.setStyleSheet(self._dbg_style(self._debug_on, T))
        self._dbg_btn.clicked.connect(self._toggle_debug)
        dbg_layout.addWidget(self._dbg_btn)

        dbg_lbl = QLabel("  Verbose RTSP/RTP/DACP logging")
        dbg_lbl.setStyleSheet(f"color: {T['muted']}; font: 11pt 'Courier New';")
        dbg_layout.addWidget(dbg_lbl)
        dbg_layout.addStretch()
        layout.addLayout(dbg_layout)

        layout.addStretch()

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"color: {T['border']}; background: {T['border']};")
        layout.addWidget(divider)
        layout.addSpacing(10)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: {T['accent']}; color: white; border: none;
                border-radius: 4px; padding: 10px 20px; font-size: 15pt; }}
            QPushButton:hover {{ background: {T['accent2']}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        open_log_btn = QPushButton("Open Log File")
        open_log_btn.clicked.connect(lambda: open_path(LOG_FILE))
        btn_layout.addWidget(open_log_btn)

        open_theme_btn = QPushButton("Open Theme File")
        open_theme_btn.clicked.connect(lambda: open_path(THEME_FILE))
        btn_layout.addWidget(open_theme_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _dbg_style(self, on: bool, T: dict) -> str:
        bg = T["teal"] if on else T["card"]
        fg = "white" if on else T["text"]
        return f"""
            QPushButton {{ background: {bg}; color: {fg}; border: none;
                border-radius: 4px; padding: 8px 16px; font: 12pt 'Courier New'; font-weight: bold; }}
            QPushButton:hover {{ background: {T['border']}; }}
        """

    @staticmethod
    def _alac_ok() -> bool:
        try:
            import av
            return True
        except ImportError:
            return False

    def _toggle_debug(self) -> None:
        self._debug_on = not self._debug_on
        self._dbg_btn.setText("DEBUG  ON" if self._debug_on else "DEBUG  OFF")
        self._dbg_btn.setStyleSheet(self._dbg_style(self._debug_on, self._theme._t))

    def _save(self) -> None:
        n = self._name_edit.text().strip()
        if n:
            self._config["device_name"] = n

        new_theme = self._theme_cb.currentText()
        theme_changed = new_theme != self._config["theme"]
        if theme_changed:
            self._config["theme"] = new_theme
            self._theme.apply(new_theme)

        new_debug = self._debug_on
        if new_debug != self._config.get("debug_mode", False):
            self._config["debug_mode"] = new_debug
            from airplay_receiver.config import set_debug_mode
            import logging
            set_debug_mode(new_debug, logging.getLogger("AirPlay"))

        sel = self._audio_cb.currentText()
        if sel in self._audio_dn:
            new_dev = self._audio_di[self._audio_dn.index(sel)]
            if new_dev != self._config["audio_device"]:
                self._config["audio_device"] = new_dev
                self._audio.set_device(new_dev)

        self.close()

        if theme_changed and self._ui_ref:
            QTimer.singleShot(50, self._ui_ref.retheme)
