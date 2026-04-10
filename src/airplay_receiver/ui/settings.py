"""
Settings dialog — frameless, themed, matches main window style.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..platform import open_path, THEME_FILE, LOG_FILE
from .buttons   import clear_cache

if TYPE_CHECKING:
    from ..config   import Config, PlayerState
    from ..audio    import AudioEngine
    from ..themes   import ThemeManager


class SettingsDialog:
    """Frameless settings window. Opened from the ⚙ gear icon."""

    def __init__(
        self,
        parent: tk.Misc,
        config: "Config",
        state:  "PlayerState",
        audio:  "AudioEngine",
        theme:  "ThemeManager",
        ui_ref=None,
    ) -> None:
        self.win     = tk.Toplevel(parent)
        self.root    = parent
        self._config = config
        self._state  = state
        self._audio  = audio
        self._theme  = theme
        self._ui_ref = ui_ref

        T = theme

        self.win.configure(bg=T["bg"])
        self.win.geometry("420x530")
        self.win.resizable(False, False)
        self.win.overrideredirect(True)
        try:
            self.win.attributes("-toolwindow", True)
        except Exception:
            pass

        # Centre over parent
        try:
            px, py = parent.winfo_x(), parent.winfo_y()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            self.win.geometry(f"420x530+{px + (pw-420)//2}+{py + (ph-530)//2}")
        except Exception:
            pass

        # Combobox style
        sty = ttk.Style(self.win)
        sty.theme_use("clam")
        sty.configure("S.TCombobox",
            fieldbackground=T.get("input_bg", T["card"]),
            background     =T.get("input_bg", T["card"]),
            foreground     =T.get("input_fg", T["text"]),
            selectbackground=T["accent"],
            selectforeground="white",
            bordercolor=T["border"], padding=5)
        sty.map("S.TCombobox",
            fieldbackground=[("readonly", T.get("input_bg", T["card"]))],
            foreground      =[("readonly", T.get("input_fg", T["text"]))])

        self._dx = [0, 0]
        self._build_titlebar()
        self._build_body()

    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self) -> None:
        T  = self._theme
        tb = tk.Frame(self.win, bg=T["tbarbg"], height=36)
        tb.pack(fill="x", side="top")
        tk.Frame(tb, bg=T["accent"], width=3).pack(side="left", fill="y")
        tk.Label(tb, text="  ⚙  SETTINGS", bg=T["tbarbg"], fg=T["muted"],
                 font=("Courier New", 7, "bold")).pack(side="left", pady=10)
        xl = tk.Label(tb, text="  ✕  ", bg=T["tbarbg"], fg=T["muted"],
                      font=("Segoe UI", 10), cursor="hand2")
        xl.pack(side="right")
        xl.bind("<Enter>", lambda e: xl.config(bg=T["accent2"], fg="white"))
        xl.bind("<Leave>", lambda e: xl.config(bg=T["tbarbg"],  fg=T["muted"]))
        xl.bind("<Button-1>", lambda e: self.win.destroy())
        tb.bind("<ButtonPress-1>",
                lambda e: self._dx.__setitem__(slice(None),
                    [e.x_root - self.win.winfo_x(),
                     e.y_root - self.win.winfo_y()]))
        tb.bind("<B1-Motion>",
                lambda e: self.win.geometry(
                    f"+{e.x_root - self._dx[0]}+{e.y_root - self._dx[1]}"))

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self) -> None:
        T = self._theme

        def row(label: str) -> None:
            tk.Label(self.win, text=label, bg=T["bg"], fg=T["teal"],
                     font=("Courier New", 7, "bold")).pack(
                     anchor="w", padx=20, pady=(14, 4))

        # Device name
        row("DEVICE NAME  (restart required)")
        self._name = tk.StringVar(value=self._config["device_name"])
        ef = tk.Frame(self.win, bg=T.get("input_bg", T["card"]),
                      highlightbackground=T["border"], highlightthickness=1)
        ef.pack(fill="x", padx=20)
        tk.Entry(ef, textvariable=self._name,
                 bg=T.get("input_bg", T["card"]),
                 fg=T.get("input_fg", T["text"]),
                 insertbackground=T["accent"], relief="flat",
                 font=("Segoe UI", 10), bd=6).pack(fill="x")

        # Theme
        row("THEME")
        names = self._theme.names()
        cur   = self._config["theme"] if self._config["theme"] in names else "Indigo Night"
        self._theme_v = tk.StringVar(value=cur)
        ttk.Combobox(self.win, textvariable=self._theme_v, values=names,
                     state="readonly", style="S.TCombobox",
                     font=("Segoe UI", 10)).pack(fill="x", padx=20)
        tk.Label(self.win, text=f"Custom themes: {THEME_FILE}",
                 bg=T["bg"], fg=T["muted"], font=("Courier New", 6)
                 ).pack(anchor="w", padx=20, pady=(3, 0))

        # Audio device
        row("AUDIO OUTPUT  (optical / S-PDIF)")
        devs      = self._audio.list_devices()
        self._dn  = ["Default (system)"] + [d[1] for d in devs]
        self._di  = [None]               + [d[0] for d in devs]
        cur_d     = (self._di.index(self._config["audio_device"])
                     if self._config["audio_device"] in self._di else 0)
        self._dv  = tk.StringVar(value=self._dn[cur_d])
        ttk.Combobox(self.win, textvariable=self._dv, values=self._dn,
                     state="readonly", style="S.TCombobox",
                     font=("Segoe UI", 10)).pack(fill="x", padx=20)

        # Audio status
        row("AUDIO STATUS")
        src = self._audio.SRC_RATE; dst = self._audio._dst_rate
        for txt, col in [
            ((f"✓  {src} Hz  (no resampling)" if src == dst
              else f"↕  {src} Hz → {dst} Hz  (resampling)"),
             T["green"] if src == dst else T["amber"]),
            (("✓  PyAV — ALAC decoding active"
              if self._alac_ok() else "✗  pip install av  — REQUIRED"),
             T["green"] if self._alac_ok() else T["accent2"]),
        ]:
            tk.Label(self.win, text=txt, bg=T["bg"], fg=col,
                     font=("Courier New", 7)).pack(anchor="w", padx=20)

        # Developer / debug
        row("DEVELOPER")
        dbg_frame = tk.Frame(self.win, bg=T["bg"])
        dbg_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._debug_v = tk.BooleanVar(value=self._config.get("debug_mode", False))
        self._dbg_btn = tk.Button(
            dbg_frame, text="", bg=T["card2"], fg=T["muted"],
            relief="flat", font=("Courier New", 7, "bold"),
            cursor="hand2", padx=10, pady=5, command=self._toggle_debug)
        self._dbg_btn.pack(side="left")
        self._update_debug_btn()
        tk.Label(dbg_frame, text="  Verbose RTSP/RTP/DACP logging",
                 bg=T["bg"], fg=T["muted"], font=("Courier New", 6)
                 ).pack(side="left")
        tk.Label(self.win, text=f"Log: {LOG_FILE}",
                 bg=T["bg"], fg=T["muted"], font=("Courier New", 6)
                 ).pack(anchor="w", padx=20, pady=(0, 2))
        tk.Button(self.win, text="Open Log File",
                  bg=T["card2"], fg=T["text2"], relief="flat",
                  font=("Courier New", 7), cursor="hand2", padx=8, pady=3,
                  command=lambda: open_path(LOG_FILE)
                  ).pack(anchor="w", padx=20)

        # Divider + buttons
        tk.Frame(self.win, bg=T["border"], height=1).pack(
            fill="x", padx=20, pady=14)
        bf = tk.Frame(self.win, bg=T["bg"])
        bf.pack()
        for text, cmd, bg_, fg_ in [
            ("Save",            self._save,                          T["accent"],  "white"),
            ("Open Theme File", lambda: open_path(THEME_FILE),       T["card2"],   T["text2"]),
            ("Cancel",          self.win.destroy,                    T["card2"],   T["text"]),
        ]:
            tk.Button(bf, text=text, command=cmd,
                      bg=bg_, fg=fg_, relief="flat",
                      activebackground=T["border"], activeforeground=T["text"],
                      font=("Segoe UI", 10), cursor="hand2",
                      padx=16, pady=9).pack(side="left", padx=5)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _alac_ok() -> bool:
        try: import av; return True
        except ImportError: return False

    def _toggle_debug(self) -> None:
        self._debug_v.set(not self._debug_v.get())
        self._update_debug_btn()

    def _update_debug_btn(self) -> None:
        T  = self._theme
        on = self._debug_v.get()
        self._dbg_btn.config(
            text=f"DEBUG  {'ON ' if on else 'OFF'}",
            bg=T["teal"] if on else T["card2"],
            fg=T["bg"]   if on else T["muted"],
        )

    def _save(self) -> None:
        n = self._name.get().strip()
        if n:
            self._config["device_name"] = n

        new_theme = self._theme_v.get()
        theme_changed = new_theme != self._config["theme"]
        if theme_changed:
            self._config["theme"] = new_theme
            self._theme.apply(new_theme)
            clear_cache()

        new_debug = self._debug_v.get()
        if new_debug != self._config.get("debug_mode", False):
            self._config["debug_mode"] = new_debug
            from ..config import set_debug_mode
            import logging
            set_debug_mode(new_debug, logging.getLogger("AirPlay"))

        sel = self._dv.get()
        if sel in self._dn:
            new_dev = self._di[self._dn.index(sel)]
            if new_dev != self._config["audio_device"]:
                self._config["audio_device"] = new_dev
                self._audio.set_device(new_dev)

        self.win.destroy()

        if theme_changed and self._ui_ref:
            self.root.after(50, self._ui_ref.retheme)
