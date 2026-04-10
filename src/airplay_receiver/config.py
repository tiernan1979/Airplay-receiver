"""
Configuration, shared player state, and logging setup.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Callable, List

from .platform import CONFIG_FILE, LOG_FILE

# ── Logging ───────────────────────────────────────────────────────────────────
_file_handler: logging.FileHandler | None = None

def setup_logging() -> logging.Logger:
    global _file_handler
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        _file_handler.setLevel(logging.WARNING)
        handlers.append(_file_handler)
    except Exception:
        pass
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    log = logging.getLogger("AirPlay")
    log.setLevel(logging.DEBUG)
    return log


_DEBUG_MODE = False

def set_debug_mode(enabled: bool, log: logging.Logger | None = None) -> None:
    global _DEBUG_MODE
    _DEBUG_MODE = enabled
    level = logging.DEBUG if enabled else logging.WARNING
    for h in logging.root.handlers:
        h.setLevel(level)
    if _file_handler:
        _file_handler.setLevel(level)
    if log:
        log.warning(f"Debug logging {'ENABLED' if enabled else 'DISABLED'}")


def dbg(msg: str, log: logging.Logger | None = None) -> None:
    if _DEBUG_MODE and log:
        log.debug(msg)


# ── Configuration ─────────────────────────────────────────────────────────────
import socket as _socket

class Config:
    """Persistent JSON configuration. Access like a dict: config['key']."""

    DEFAULTS: dict = {
        "device_name": f"AirPlay-{_socket.gethostname()}",
        "volume": 80,
        "audio_device": None,
        "start_minimised": False,
        "theme": "Indigo Night",
        "debug_mode": False,
    }

    def __init__(self, path: Path = CONFIG_FILE):
        self._path = path
        self.data: dict = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            if self._path.exists():
                loaded = json.loads(self._path.read_text())
                self.data.update(loaded)
        except Exception:
            pass

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self.data, indent=2))
        except Exception:
            pass

    def __getitem__(self, k: str):
        return self.data[k]

    def __setitem__(self, k: str, v) -> None:
        self.data[k] = v
        self.save()

    def get(self, key: str, default=None):
        return self.data.get(key, default)


# ── Player State ──────────────────────────────────────────────────────────────
class PlayerState:
    """
    Shared mutable state. Thread-safe dirty-flag pattern:
      • background threads call state.update() or state.mark_dirty()
      • UI thread polls state.consume_dirty() in its animation tick
    """

    def __init__(self) -> None:
        self.title: str       = ""
        self.artist: str      = ""
        self.album: str       = ""
        self.artwork          = None
        self.volume: int      = 80
        self.playing: bool    = False
        self.connected: bool  = False
        self.client_ip: str   = ""
        self.port: int        = 7000
        self.dacp_id: str     = ""
        self.active_remote: str = ""
        self.dacp_ip: str     = ""
        self.dacp_port: int   = 0
        self.codec: str       = ""
        self._cbs: List[Callable] = []
        self._dirty           = False
        self._lock            = threading.Lock()

    def update(self, **kw) -> None:
        with self._lock:
            changed = any(getattr(self, k, None) != v for k, v in kw.items())
            for k, v in kw.items():
                setattr(self, k, v)
            if changed:
                self._dirty = True
                for cb in self._cbs:
                    try:
                        cb()
                    except Exception:
                        pass

    def mark_dirty(self) -> None:
        """Force a UI refresh without value comparison."""
        with self._lock:
            self._dirty = True

    def consume_dirty(self) -> bool:
        """Returns True and clears flag. Call from UI thread only."""
        with self._lock:
            if self._dirty:
                self._dirty = False
                return True
            return False

    def on_change(self, cb: Callable) -> None:
        self._cbs.append(cb)


# Module-level singletons (initialised in main())
log:    logging.Logger | None = None
config: Config | None         = None
state:  PlayerState | None    = None


def init() -> tuple[logging.Logger, Config, PlayerState]:
    """Initialise module singletons. Call once at startup."""
    global log, config, state
    log    = setup_logging()
    config = Config()
    state  = PlayerState()
    if config.get("debug_mode"):
        set_debug_mode(True, log)
    return log, config, state
