"""
Cross-platform compatibility helpers.

Centralises every OS-specific decision so the rest of the code is clean:
  - Data/config/log paths
  - Opening files in the system default app
  - Window hints for Qt (lazy imports for testability)
"""
from __future__ import annotations

import os
import sys
import platform
import subprocess
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX   = platform.system() == "Linux"
IS_MAC     = platform.system() == "Darwin"

# ── App data directory ────────────────────────────────────────────────────────
def _app_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        return base / "AirPlayReceiver"
    elif IS_LINUX:
        system_dir = Path("/var/lib/airplay-receiver")
        try:
            system_dir.mkdir(parents=True, exist_ok=True)
            (system_dir / ".write_test").touch()
            (system_dir / ".write_test").unlink()
            return system_dir
        except (PermissionError, OSError):
            pass
        try:
            from platformdirs import user_data_dir
            return Path(user_data_dir("airplay-receiver", appauthor=False))
        except ImportError:
            return Path.home() / ".local" / "share" / "airplay-receiver"
    elif IS_MAC:
        return Path.home() / "Library" / "Application Support" / "AirPlayReceiver"
    else:
        return Path.home() / ".airplay-receiver"


def setup_app_dir() -> Path:
    d = _app_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).parent


APP_DIR     = setup_app_dir()
CONFIG_FILE = APP_DIR / "config.json"
THEME_FILE  = APP_DIR / "themes.json"
LOG_FILE    = APP_DIR / "airplay_receiver.log"


# ── Open file/folder in system default app ────────────────────────────────────
def open_path(path: Path) -> None:
    try:
        if IS_WINDOWS:
            os.startfile(str(path))
        elif IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            for cmd in ["xdg-open", "gedit", "nano", "vi"]:
                try:
                    subprocess.Popen([cmd, str(path)])
                    return
                except FileNotFoundError:
                    continue
    except Exception:
        pass


# ── Qt window attribute helpers (lazy imports) ───────────────────────────────
def set_window_no_taskbar(window) -> None:
    """Hide window from taskbar/panel, keeping it in system tray."""
    from PySide6.QtCore import Qt
    flags = window.windowFlags()
    if IS_WINDOWS:
        window.setWindowFlags(flags | Qt.Tool | Qt.FramelessWindowHint)
    elif IS_LINUX:
        window.setWindowFlags(flags | Qt.Tool | Qt.FramelessWindowHint)
        try:
            window.setAttribute(Qt.WA_X11NetWmWindowTypeUtility, True)
        except Exception:
            pass


def set_window_alpha(window, alpha: float) -> None:
    try:
        window.setWindowOpacity(alpha)
    except Exception:
        pass


# ── Systemd service file (Linux) ──────────────────────────────────────────────
SYSTEMD_SERVICE = """\
[Unit]
Description=AirPlay Receiver
After=network.target sound.target

[Service]
Type=simple
ExecStart={exe}
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
"""
