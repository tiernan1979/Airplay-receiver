"""
AirPlay Receiver — entry point.
python -m airplay_receiver   or   airplay-receiver (installed script)
"""
from __future__ import annotations

import threading
import tkinter as tk
import time
import subprocess, sys, os

from airplay_receiver.audio import AudioEngine, AUDIO_AVAILABLE, AV_AVAILABLE
from airplay_receiver.config import init as config_init
from airplay_receiver.dacp import DacpDiscovery, DacpRemote
from airplay_receiver.platform import THEME_FILE
from airplay_receiver.raop import MdnsAdvertiser, RaopServer, find_free_tcp
from airplay_receiver.themes import ThemeManager, write_default_theme_file
from airplay_receiver.updater.ab_manager import swap_versions, get_executable

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

PREFERRED_PORT = 7000


# ── System tray ───────────────────────────────────────────────────────────────
def _tray_icon_img(accent: str = "#8b5cf6") -> "Image.Image":
    from PIL import Image, ImageDraw
    from .ui.colours import rgb as _rgb
    sz  = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    r, g, b = _rgb(accent)
    for i in range(sz // 2, 0, -1):
        t  = i / (sz // 2)
        factor = 0.8 + 0.4 * (1 - t)
        d.ellipse([sz//2-i, sz//2-i, sz//2+i, sz//2+i],
                  fill=(min(255, int(r*factor)),
                        min(255, int(g*factor)),
                        min(255, int(b*factor)), 255))
    d.text((sz//2, sz//2), "♫", fill=(255, 255, 255, 200), anchor="mm")
    return img


def run_tray(ui) -> None:
    if not TRAY_AVAILABLE:
        return
    from .themes import ThemeManager
    T   = ui._theme
    img = _tray_icon_img(T["accent"])
    menu = pystray.Menu(
        pystray.MenuItem("Open",  lambda *_: ui.root.after(0, ui.show), default=True),
        pystray.MenuItem("Quit",  lambda icon, *_: (icon.stop(), ui.root.after(0, ui.quit_app))),
    )
    icon = pystray.Icon("AirPlay Receiver", img, "AirPlay Receiver", menu)
    icon.run()

# ── Apply Update on Start ──────────────────────────────────────────────────────────────────────

def apply_pending_update():
    import shutil,os
    flag = os.path.join(tempfile.gettempdir(), "airplay_pending_update")

    if not os.path.exists(flag):
        return

    with open(flag) as f:
        path = f.read().strip()

    os.remove(flag)

    install_dir = os.path.dirname(sys.executable)

    # simple replace strategy
    shutil.copy(path, os.path.join(install_dir, "AirPlayReceiver.exe"))

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    import logging

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

    # UI
    root = tk.Tk()
    root.withdraw()

    from airplay_receiver.ui.main_window import ModernUI
    ui = ModernUI(root, config, state, audio, dacp_remote, theme)

    if not config["start_minimised"]:
        root.after(200, ui.show)

    if TRAY_AVAILABLE:
        threading.Thread(target=run_tray, args=(ui,), daemon=True, name="tray").start()

    updater = BackgroundUpdater(ui)
    updater.start()

    try:
        root.mainloop()
    finally:
        log.warning("Shutdown")
        mdns.stop()
        raop.stop()
        audio.stop()
        config.save()


if __name__ == "__main__":

    # try swap first (safe point)
    swapped = swap_versions()

    try:
        if swapped:
            exe = get_executable()
            subprocess.Popen([exe])
            sys.exit(0)
    except Exception:
        pass

    main()