"""
DACP (Digital Audio Control Protocol) — remote control of Music Assistant.

Discovers the MA DACP server via mDNS, then sends HTTP commands:
  - play/pause toggle
  - next/previous track
  - set volume
"""
from __future__ import annotations

import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import PlayerState


class DacpDiscovery:
    """Browse _dacp._tcp.local. to find MA's DACP port."""

    def __init__(self) -> None:
        self._started = False

    def start(self, state: "PlayerState") -> None:
        if self._started:
            return
        try:
            from zeroconf import ServiceBrowser, Zeroconf

            zc = Zeroconf()

            class _Listener:
                def add_service(self, zc, type_, name):
                    info = zc.get_service_info(type_, name)
                    if info and info.parsed_addresses():
                        import socket
                        dacp_id = getattr(state, "dacp_id", "")
                        if dacp_id and dacp_id.upper() not in name.upper():
                            return
                        ip   = info.parsed_addresses()[0]
                        port = info.port
                        state.update(dacp_ip=ip, dacp_port=port)
                        import logging
                        logging.getLogger("AirPlay").warning(
                            f"DACP: {ip}:{port}"
                        )

                def remove_service(self, *_): pass
                def update_service(self, *_): pass

            ServiceBrowser(zc, "_dacp._tcp.local.", _Listener())
            self._started = True
        except Exception:
            pass


class DacpRemote:
    """Send HTTP commands to the MA DACP server."""

    def __init__(self, state: "PlayerState") -> None:
        self._state = state

    def _send(self, cmd: str) -> None:
        s = self._state
        if not s.active_remote or not s.dacp_ip or not s.dacp_port:
            return
        url = f"http://{s.dacp_ip}:{s.dacp_port}/ctrl-int/1/{cmd}"
        try:
            req = urllib.request.Request(
                url,
                headers={"Active-Remote": s.active_remote, "Connection": "close"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                import logging
                logging.getLogger("AirPlay").debug(
                    f"DACP /{cmd} → {resp.status}"
                )
        except Exception as exc:
            import logging
            logging.getLogger("AirPlay").debug(f"DACP /{cmd}: {exc}")

    def _fire(self, cmd: str) -> None:
        threading.Thread(target=self._send, args=(cmd,), daemon=True).start()

    def play_pause(self) -> None:
        self._send("playpause")

    def next_track(self) -> None:
        self._fire("nextitem")

    def prev_track(self) -> None:
        self._fire("previtem")

    def set_volume(self, pct: int) -> None:
        db = -30.0 + (pct / 100.0) * 30.0
        self._fire(f"setproperty?dmcp.device-volume={db:.2f}")
