"""
AirPlay Receiver — entry point.
python -m airplay_receiver   or   airplay-receiver (installed script)
"""
from __future__ import annotations

import sys
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QBrush
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from airplay_receiver.audio import AudioEngine, AUDIO_AVAILABLE, AV_AVAILABLE
from airplay_receiver.config import init as config_init
from airplay_receiver.dacp import DacpDiscovery, DacpRemote
from airplay_receiver.platform import THEME_FILE
from airplay_receiver.raop import MdnsAdvertiser, RaopServer, find_free_tcp
from airplay_receiver.themes import ThemeManager, write_default_theme_file

PREFERRED_PORT = 7000


# ── Apply Update on Start ──────────────────────────────────────────────────────
def apply_pending_update():
    import shutil, tempfile
    flag = os.path.join(tempfile.gettempdir(), "airplay_pending_update")

    if not os.path.exists(flag):
        return

    with open(flag) as f:
        path = f.read().strip()

    os.remove(flag)

    install_dir = os.path.dirname(sys.executable)
    shutil.copy(path, os.path.join(install_dir, "AirPlayReceiver.exe"))


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    import logging

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # ── Resources ──────────────────────────────────────────────────────────
    log, config, state = config_init()

    if not AUDIO_AVAILABLE:
        log.warning("sounddevice/numpy not installed — no audio output")
    if not AV_AVAILABLE:
        log.warning("PyAV not installed — ALAC decoding disabled (silence)")

    # Theme
    write_default_theme_file(THEME_FILE)
    theme = ThemeManager(THEME_FILE)
    theme.apply(config["theme"])

    # Audio
    audio = AudioEngine(
        initial_volume=config["volume"],
        device=config["audio_device"],
    )
    audio.start()
    audio.set_volume(config["volume"])

    # DACP
    dacp_disc   = DacpDiscovery()
    dacp_remote = DacpRemote(state)
    dacp_disc.start(state)

    # RAOP server
    try:
        port = find_free_tcp(PREFERRED_PORT)
    except RuntimeError:
        port = PREFERRED_PORT
    state.update(port=port)

    raop = RaopServer(port, state, config, audio, dacp_remote)
    if not raop.start():
        log.error(f"Cannot bind TCP {port}")

    mdns = MdnsAdvertiser(config["device_name"], port)
    mdns.start()

    log.warning("=" * 55)
    log.warning(f"AirPlay Receiver v11.0 — port {port}")
    log.warning(f"PyAV:  {'✓' if AV_AVAILABLE else '✗ pip install av'}")
    log.warning(f"Audio: {'✓' if AUDIO_AVAILABLE else '✗ pip install sounddevice numpy'}")
    log.warning("=" * 55)

    # ── UI ─────────────────────────────────────────────────────────────────
    from airplay_receiver.ui.main_window import ModernUI
    ui = ModernUI(config, state, audio, dacp_remote, theme)

    if not config["start_minimised"]:
        QTimer.singleShot(200, ui.show)

    # ── System tray ────────────────────────────────────────────────────────
    tray_icon = QIcon()
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
        icon_path = os.path.join(base, "app.ico")
    else:
        icon_path = "install/windows/app.ico"

    if os.path.exists(icon_path):
        tray_icon = QIcon(icon_path)
    else:
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(p.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#8b5cf6")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, 28, 28)
        p.setPen(QColor("white"))
        p.drawText(0, 0, 32, 32, Qt.AlignCenter, "♪")
        p.end()
        tray_icon = QIcon(pix)

    tray = QSystemTrayIcon(tray_icon, app)
    tray.setToolTip("AirPlay Receiver")

    tray_menu = QMenu()
    open_action = QAction("Open", tray_menu)
    open_action.triggered.connect(ui.show)
    tray_menu.addAction(open_action)
    tray_menu.setDefaultAction(open_action)

    quit_action = QAction("Quit", tray_menu)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)

    tray.setContextMenu(tray_menu)
    tray.show()

    # ── Cleanup on quit ────────────────────────────────────────────────────
    def cleanup():
        log.warning("Shutdown")
        mdns.stop()
        raop.stop()
        audio.stop()
        config.save()

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
