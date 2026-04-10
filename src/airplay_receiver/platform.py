"""
Cross-platform compatibility helpers.

Centralises every OS-specific decision so the rest of the code is clean:
  - Data/config/log paths
  - Opening files in the system default app
  - Tray icon support detection
  - Tkinter window hints
"""
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
    """
    Returns the platform-appropriate writable app-data directory.

    Windows : C:\\ProgramData\\AirPlayReceiver
    Linux   : /var/lib/airplay-receiver  (or ~/.local/share/airplay-receiver)
    macOS   : ~/Library/Application Support/AirPlayReceiver
    """
    if IS_WINDOWS:
        base = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
        return base / "AirPlayReceiver"
    elif IS_LINUX:
        # Try system-wide first (writable when installed as service)
        system_dir = Path("/var/lib/airplay-receiver")
        try:
            system_dir.mkdir(parents=True, exist_ok=True)
            # Test write access
            (system_dir / ".write_test").touch()
            (system_dir / ".write_test").unlink()
            return system_dir
        except (PermissionError, OSError):
            pass
        # Fall back to user-local
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
    """Create app dir and return it. Falls back to script directory on error."""
    d = _app_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        # Last resort: next to the executable / script
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).parent


APP_DIR     = setup_app_dir()
CONFIG_FILE = APP_DIR / "config.json"
THEME_FILE  = APP_DIR / "themes.json"
LOG_FILE    = APP_DIR / "airplay_receiver.log"


# ── Open file/folder in system default app ────────────────────────────────────
def open_path(path: Path) -> None:
    """Open a file or folder using the OS default application."""
    try:
        if IS_WINDOWS:
            os.startfile(str(path))
        elif IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            # Linux — try xdg-open, then fallback editors
            for cmd in ["xdg-open", "gedit", "nano", "vi"]:
                try:
                    subprocess.Popen([cmd, str(path)])
                    return
                except FileNotFoundError:
                    continue
    except Exception:
        pass


# ── Tkinter window attribute helpers ─────────────────────────────────────────
def set_window_no_taskbar(root) -> None:
    """Hide window from taskbar/panel, keeping it in the system tray only."""
    try:
        if IS_WINDOWS:
            root.attributes("-toolwindow", True)
        elif IS_LINUX:
            # X11: skip_taskbar hint
            root.after(100, lambda: _linux_skip_taskbar(root))
        # macOS: handled by LSUIElement in Info.plist for frozen apps
    except Exception:
        pass


def _linux_skip_taskbar(root) -> None:
    try:
        root.tk.call("wm", "attributes", ".", "-type", "utility")
    except Exception:
        pass


def set_window_alpha(root, alpha: float) -> None:
    try:
        root.attributes("-alpha", alpha)
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
