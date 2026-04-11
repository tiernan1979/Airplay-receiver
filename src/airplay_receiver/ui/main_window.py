"""
Main application window — frameless, blurred-art background, canvas-based UI.
"""
from __future__ import annotations

import gc
import math
import threading
import tkinter as tk
from typing import TYPE_CHECKING

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from airplay_receiver.platform import IS_WINDOWS, set_window_no_taskbar, set_window_alpha
from airplay_receiver.ui.buttons   import make_sphere, make_small_circle, clear_cache
from airplay_receiver.ui.colours   import rgb as _rgb, blend as _blend
from airplay_receiver.ui.settings  import SettingsDialog
from airplay_receiver.ui.widgets   import CanvasSlider

if TYPE_CHECKING:
    from airplay_receiver.audio   import AudioEngine
    from airplay_receiver.config  import Config, PlayerState
    from airplay_receiver.dacp    import DacpRemote
    from airplay_receiver.themes  import ThemeManager


class ModernUI:
    W   = 370
    H   = 530
    TH  = 36    # titlebar height
    ART = 176   # artwork circle diameter

    def __init__(
        self,
        root: tk.Tk,
        config: "Config",
        state:  "PlayerState",
        audio:  "AudioEngine",
        dacp:   "DacpRemote",
        theme:  "ThemeManager",
    ) -> None:
        import logging
        self._log    = logging.getLogger("AirPlay")
        self.root    = root
        self._config = config
        self._state  = state
        self._audio  = audio
        self._dacp   = dacp
        self._theme  = theme
        self._refs: dict = {}
        self._pulse  = 0.0
        self._pulse_id: str | None = None
        self._drag_x = self._drag_y = 0
        self._bg_art = None
        self._last_art = None
        self._btn_state: dict = {}
        self._transport_rects: dict = {}
        self._transport_bound = False
        self._tick_count  = 0
        self._title_str   = ""
        self._title_off   = 0.0
        self._title_dir   = 1
        self._title_pause = 80
        self._title_y     = 0
        self._title_item: int | None = None
        self._panel_y     = 0
        self._vol_timer: str | None = None

        self._setup_window()
        T = theme
        self._cv = tk.Canvas(root, width=self.W, height=self.H,
                             bg=T["bg"], highlightthickness=0)
        self._cv.place(x=0, y=0, width=self.W, height=self.H)
        self._draw_bg(None)
        self._build_titlebar()
        self._build_body()

        # Wire state → tick-based refresh
        state.on_change(lambda: None)   # _tick polls dirty flag
        self._refresh()
        self._tick()

    # ── Window setup ──────────────────────────────────────────────────────────
    def _setup_window(self) -> None:
        T = self._theme
        self.root.title("AirPlay Receiver")
        self.root.configure(bg=T["bg"])
        self.root.resizable(False, False)
        self.root.geometry(f"{self.W}x{self.H}")
        self.root.overrideredirect(True)
        set_window_no_taskbar(self.root)
        set_window_alpha(self.root, 0.97)
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(
                f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}"
            )
        except Exception:
            pass

    # ── Background ────────────────────────────────────────────────────────────
    def _draw_bg(self, artwork) -> None:
        if not PIL_AVAILABLE:
            return
        T  = self._theme
        W, H  = self.W, self.H
        panel_y = self._panel_y or int(H * 0.61)

        if artwork:
            try:
                src = getattr(artwork, "im", artwork)
                bg  = src.convert("RGB").resize((W // 2, H // 2), Image.BILINEAR)
                bg  = bg.filter(ImageFilter.GaussianBlur(13))
                bg  = ImageEnhance.Brightness(bg).enhance(0.28)
                bg  = ImageEnhance.Color(bg).enhance(0.6)
                bg  = bg.resize((W, H), Image.BILINEAR)
                del src
            except Exception:
                artwork = None

        if not artwork:
            bg   = Image.new("RGB", (W, H), _rgb(T["bg"]))
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(glow)
            rv, gv, bv = _rgb(T["accent"])
            for r in range(120, 0, -6):
                t = r / 120; a = int(18 * (1 - t) * t * 4)
                gd.ellipse([-20, -10, r*2-20, r*2-10], fill=(rv, gv, bv, a))
            rv2, gv2, bv2 = _rgb(T["accent2"])
            for r in range(100, 0, -6):
                t = r / 100; a = int(14 * (1 - t) * t * 4)
                gd.ellipse([W-r*2+20, H-r*2+10, W+20, H+10], fill=(rv2, gv2, bv2, a))
            bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")
            del glow

        panel = Image.new("RGB", (W, H - panel_y), _rgb(T["bg"]))
        bg.paste(panel, (0, panel_y))
        del panel

        photo = ImageTk.PhotoImage(bg)
        del bg; gc.collect()

        self._refs["bg"] = photo
        self._cv.delete("bg")
        self._cv.create_image(0, 0, anchor="nw", image=photo, tags="bg")
        self._cv.tag_lower("bg")

    # ── Titlebar ──────────────────────────────────────────────────────────────
    def _build_titlebar(self) -> None:
        T  = self._theme
        TH = self.TH; W = self.W
        self._tb = tk.Frame(self.root, bg=T["tbarbg"], height=TH)
        tb = self._tb
        tb.place(x=0, y=0, width=W, height=TH)
        tb.lift()
        self._tb_accent = tk.Frame(tb, bg=T["accent"], width=3)
        self._tb_accent.pack(side="left", fill="y")
        self._tb_lbl = tk.Label(tb, text="  ♫  AIRPLAY RECEIVER",
                                bg=T["tbarbg"], fg=T["muted"],
                                font=("Courier New", 7, "bold"))
        self._tb_lbl.pack(side="left")
        xl = tk.Label(tb, text="  ✕  ", bg=T["tbarbg"], fg=T["muted"],
                      font=("Segoe UI", 10), cursor="hand2")
        xl.pack(side="right")
        xl.bind("<Enter>",    lambda e: xl.config(bg=T["accent2"], fg="white"))
        xl.bind("<Leave>",    lambda e: xl.config(bg=T["tbarbg"],  fg=T["muted"]))
        xl.bind("<Button-1>", lambda e: self.quit_app())
        self._tb_xl = xl
        ml = tk.Label(tb, text="  ─  ", bg=T["tbarbg"], fg=T["muted"],
                      font=("Segoe UI", 10), cursor="hand2")
        ml.pack(side="right")
        ml.bind("<Enter>",    lambda e: ml.config(bg=T["card2"], fg=T["text"]))
        ml.bind("<Leave>",    lambda e: ml.config(bg=T["tbarbg"], fg=T["muted"]))
        ml.bind("<Button-1>", lambda e: self._minimise())
        self._tb_ml = ml
        tb.bind("<ButtonPress-1>", self._drag_start)
        tb.bind("<B1-Motion>",     self._drag_move)

    def _drag_start(self, e: tk.Event) -> None:
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _drag_move(self, e: tk.Event) -> None:
        self.root.geometry(f"+{e.x_root-self._drag_x}+{e.y_root-self._drag_y}")

    def _minimise(self) -> None:
        self.root.withdraw()

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self) -> None:
        T = self._theme
        W = self.W; y = self.TH

        # Status row
        y += 8
        self._sdot_item  = self._cv.create_text(
            17, y+2, text="●", fill=T["muted"],
            font=("Segoe UI", 9), anchor="nw")
        self._stxt_item  = self._cv.create_text(
            32, y, text="STANDBY", fill=T["muted"],
            font=("Courier New", 7, "bold"), anchor="nw")
        self._codec_item = self._cv.create_text(
            W-10, y, text="", fill=T["teal"],
            font=("Courier New", 7, "bold"), anchor="ne")
        y += 20

        # Artwork circle
        sz       = self.ART
        ax       = (W - sz) // 2
        ay       = y
        ring_pad = 12
        self._art_ax  = ax - ring_pad - 5
        self._art_ay  = ay - ring_pad - 5
        self._art_off = ring_pad + 5
        self._art_sz  = sz
        rx0, ry0 = ax - ring_pad, ay - ring_pad
        rx1, ry1 = ax + sz + ring_pad, ay + sz + ring_pad
        self._ring = self._cv.create_oval(
            rx0, ry0, rx1, ry1,
            outline=T["accent"], width=1, dash=(4, 9))
        self._draw_default_art()
        y += sz + 10

        # Title (scrolled by _tick)
        self._title_y    = y + 13
        self._title_item = self._cv.create_text(
            W // 2, self._title_y, text="",
            fill=T["text"], font=("Segoe UI", 12, "bold"), anchor="center")
        y += 28

        # Artist / album
        self._info_item = self._cv.create_text(
            W // 2, y + 9, text="", fill=T["muted"],
            font=("Segoe UI", 9), anchor="center", width=W - 24)
        y += 22

        # Panel start — baked into background image
        self._panel_y = y
        self._draw_bg(None)

        # Divider
        y += 4
        self._div1 = self._cv.create_line(20, y, W-20, y,
                                          fill=T["border"], width=1)
        y += 10

        # Volume
        self._cv.create_text(20, y+8, text="VOL", fill=T["teal"],
                             font=("Courier New", 7, "bold"),
                             anchor="w", tags="vol_lbl")
        self._vv = tk.IntVar(value=self._state.volume)
        self._vol_slider = CanvasSlider(
            self._cv, var=self._vv,
            cmd=self._on_vol, width=W - 104, theme=dict(self._theme._t))
        self._vol_slider.place(x=52, y=y)
        self._vol_pct = self._cv.create_text(
            W-6, y+8, text=f"{self._state.volume}%", fill=T["text2"],
            font=("Courier New", 9), anchor="e", tags="vol_pct")
        y += 28

        # Transport buttons
        self._btn_y  = y
        sm_t = 44 + 16; pl_t = 64 + 20; gap = 8
        self._btn_bx = (W - (sm_t + gap + pl_t + gap + sm_t)) // 2
        self._btn_state = {}
        self._draw_transport()
        y += 84

        # Bottom bar
        self._div2      = self._cv.create_line(0, y, W, y,
                                               fill=T["border"], width=1)
        self._devl_item = self._cv.create_text(
            12, y+12, text=f"{self._config['device_name']}  ·  port {self._state.port}",
            fill=T["muted"], font=("Courier New", 7), anchor="w", tags="devl")
        self._gear_item = self._cv.create_text(
            W-14, y+12, text="⚙", fill=T["muted"],
            font=("Segoe UI", 11), anchor="e", tags="gear_btn")
        self._cv.tag_bind("gear_btn", "<Enter>",
            lambda e: self._cv.itemconfig("gear_btn", fill=T["text"]))
        self._cv.tag_bind("gear_btn", "<Leave>",
            lambda e: self._cv.itemconfig("gear_btn", fill=T["muted"]))
        self._cv.tag_bind("gear_btn", "<Button-1>",
            lambda e: SettingsDialog(
                self.root, self._config, self._state,
                self._audio, self._theme, ui_ref=self))

        actual_h = y + 34
        if actual_h != self.H:
            self.H = actual_h
            self.root.geometry(f"{self.W}x{self.H}")
            self._cv.config(height=self.H, width=self.W)
            self._draw_bg(None)

    # ── Artwork drawing ───────────────────────────────────────────────────────
    def _draw_default_art(self) -> None:
        if not PIL_AVAILABLE: return
        T   = self._theme
        sz  = self._art_sz; r = sz // 2
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        cx  = cy = r

        for ri in range(r, 0, -1):
            v = int(12 * (1 - (ri / r) * 0.3))
            d.ellipse([cx-ri, cy-ri, cx+ri, cy+ri], fill=(v, v, v, 255))
        tr, tg, tb = _rgb(T["teal"])
        bx1, by1 = cx - int(r*0.30), cy - int(r*0.30)
        for i in range(int(r*0.9), 0, -2):
            t = i / (r*0.9); a = int(130 * (1-t)**1.0)
            d.ellipse([bx1-i, by1-i, bx1+i, by1+i], fill=(tr, tg, tb, a))
        ar, ag, ab = _rgb(T["accent"])
        bx2, by2 = cx + int(r*0.22), cy + int(r*0.22)
        for i in range(int(r*0.7), 0, -2):
            t = i / (r*0.7); a = int(80 * (1-t)**1.2)
            d.ellipse([bx2-i, by2-i, bx2+i, by2+i], fill=(ar, ag, ab, a))

        mask = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, sz, sz], fill=255)
        img.putalpha(mask)

        note = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        nd   = ImageDraw.Draw(note)
        mr, mg, mb = _rgb(T["text2"])
        nd.text((cx, cy), "♫", fill=(mr, mg, mb, 220), anchor="mm")
        note.putalpha(mask)
        img = Image.alpha_composite(img, note)

        photo = ImageTk.PhotoImage(img); del img, note, mask
        self._refs["dart"] = photo
        self._cv.delete("art")
        ax = (self.W - self._art_sz) // 2
        ay = self._art_ay + self._art_off
        self._cv.create_image(ax, ay, anchor="nw", image=photo, tags="art")
        self._cv.tag_raise("art")

    def _draw_art_image(self, artwork) -> None:
        if not PIL_AVAILABLE or not artwork: return
        sz   = self._art_sz
        src  = getattr(artwork, "im", artwork)
        img  = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        art  = src.convert("RGBA").resize((sz, sz), Image.LANCZOS)
        mask = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, sz, sz], fill=255)
        art.putalpha(mask)
        img.paste(art, (0, 0), art)
        photo = ImageTk.PhotoImage(img); del img, art, mask
        self._refs["art"] = photo
        self._cv.delete("art")
        ax = (self.W - sz) // 2; ay = self._art_ay + self._art_off
        self._cv.create_image(ax, ay, anchor="nw", image=photo, tags="art")
        self._cv.tag_raise("art")

    # ── Transport buttons ─────────────────────────────────────────────────────
    def _draw_transport(self) -> None:
        T   = self._theme
        y   = self._btn_y; bx = self._btn_bx; bs = self._btn_state
        sm  = 44; sm_t = sm + 16; pl = 64; pl_t = pl + 20; gap = 8

        px_prev = bx
        px_play = bx + sm_t + gap
        px_next = px_play + pl_t + gap

        for tag in ("btn_prev","icon_prev","btn_play","icon_play","btn_next","icon_next"):
            self._cv.delete(tag)

        # Prev
        prev_img   = make_small_circle(sm, T["card2"], T["accent"],
                                       bs.get("hover_prev"), bs.get("press_prev"))
        if prev_img:
            prev_photo = ImageTk.PhotoImage(prev_img)
            self._refs["btn_prev"] = prev_photo
            self._cv.create_image(px_prev, y+10, anchor="nw",
                                  image=prev_photo, tags="btn_prev")
        self._cv.create_text(px_prev + sm_t//2, y+10 + sm_t//2,
                             text="⏮",
                             fill=T["text"] if bs.get("hover_prev") else T["text2"],
                             font=("Segoe UI", 14, "bold"), tags="icon_prev")

        # Play/pause sphere
        col = T["accent2"] if self._state.playing else T["accent"]
        if bs.get("hover_play"):
            col = _blend(col, "#ffffff", 0.15)
        play_img   = make_sphere(pl, col, T["accent2"] if self._state.playing else T["accent"],
                                 pressed=bs.get("press_play", False))
        if play_img:
            play_photo = ImageTk.PhotoImage(play_img)
            self._refs["btn_play"] = play_photo
            self._cv.create_image(px_play, y, anchor="nw",
                                  image=play_photo, tags="btn_play")
        icon = "⏸" if self._state.playing else "▶"
        self._cv.create_text(px_play + pl_t//2, y + pl_t//2,
                             text=icon, fill="white",
                             font=("Segoe UI", 20, "bold"), tags="icon_play")

        # Next
        next_img   = make_small_circle(sm, T["card2"], T["accent"],
                                       bs.get("hover_next"), bs.get("press_next"))
        if next_img:
            next_photo = ImageTk.PhotoImage(next_img)
            self._refs["btn_next"] = next_photo
            self._cv.create_image(px_next, y+10, anchor="nw",
                                  image=next_photo, tags="btn_next")
        self._cv.create_text(px_next + sm_t//2, y+10 + sm_t//2,
                             text="⏭",
                             fill=T["text"] if bs.get("hover_next") else T["text2"],
                             font=("Segoe UI", 14, "bold"), tags="icon_next")

        # Hit rects
        self._transport_rects = {
            "prev": (px_prev, y+10, px_prev+sm_t, y+10+sm_t),
            "play": (px_play, y,    px_play+pl_t, y+pl_t),
            "next": (px_next, y+10, px_next+sm_t, y+10+sm_t),
        }

        for tag in ("btn_prev","icon_prev","btn_play","icon_play","btn_next","icon_next"):
            try: self._cv.tag_raise(tag)
            except Exception: pass

        if not self._transport_bound:
            self._transport_bound = True
            self._cv.bind("<Motion>",          self._on_transport_motion)
            self._cv.bind("<ButtonPress-1>",   self._on_transport_press)
            self._cv.bind("<ButtonRelease-1>", self._on_transport_release)
            self._cv.bind("<Leave>",           lambda e: self._clear_hover())

    def _clear_hover(self) -> None:
        changed = any(self._btn_state.get(k) for k in
                      ("hover_prev", "hover_play", "hover_next"))
        for k in ("hover_prev", "hover_play", "hover_next"):
            self._btn_state[k] = False
        if changed: self._draw_transport()

    def _transport_hit(self, x: int, y: int) -> str | None:
        for name, (x0, y0, x1, y1) in self._transport_rects.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def _on_transport_motion(self, e: tk.Event) -> None:
        hit = self._transport_hit(e.x, e.y)
        changed = False
        for k, btn in (("hover_prev","prev"),("hover_play","play"),("hover_next","next")):
            want = btn == hit
            if self._btn_state.get(k) != want:
                self._btn_state[k] = want; changed = True
        if changed: self._draw_transport()

    def _on_transport_press(self, e: tk.Event) -> None:
        hit = self._transport_hit(e.x, e.y)
        if hit:
            self._btn_state[f"press_{hit}"] = True
            self._draw_transport()

    def _on_transport_release(self, e: tk.Event) -> None:
        hit = self._transport_hit(e.x, e.y)
        for k in ("press_prev", "press_play", "press_next"):
            self._btn_state[k] = False
        if hit == "prev":  self._dacp.prev_track()
        elif hit == "play": self._play_pause()
        elif hit == "next": self._dacp.next_track()
        self._draw_transport()

    # ── Refresh ───────────────────────────────────────────────────────────────
    def _refresh(self) -> None:
        s = self._state
        T = self._theme

        title = s.title or ("Playing…" if s.playing else "")
        if title != self._title_str:
            self._title_str   = title
            self._title_off   = 0.0
            self._title_dir   = 1
            self._title_pause = 80
            if self._title_item:
                self._cv.itemconfig(self._title_item, text=title)

        parts = [p for p in [s.artist, s.album] if p]
        self._cv.itemconfig(self._info_item, text="  ·  ".join(parts))

        self._draw_transport()

        sv = s.volume
        if self._vv.get() != sv:
            self._vv.set(sv)
        self._cv.itemconfig("vol_pct", text=f"{sv}%")
        self._cv.itemconfig("devl",
                            text=f"{self._config['device_name']}  ·  port {s.port}")
        self._cv.itemconfig(self._codec_item, text=s.codec or "")

        if s.connected and s.playing:
            self._cv.itemconfig(self._sdot_item, fill=T["green"])
            self._cv.itemconfig(self._stxt_item, text="PLAYING", fill=T["green"])
        elif s.connected:
            self._cv.itemconfig(self._sdot_item, fill=T["amber"])
            self._cv.itemconfig(self._stxt_item, text="CONNECTED", fill=T["amber"])
        else:
            self._cv.itemconfig(self._sdot_item, fill=T["muted"])
            self._cv.itemconfig(self._stxt_item, text="STANDBY", fill=T["muted"])

        if s.artwork and PIL_AVAILABLE:
            if s.artwork is not self._last_art:
                self._last_art = s.artwork
                try:
                    self._draw_art_image(s.artwork)
                except Exception as exc:
                    self._log.warning(f"draw_art_image: {exc}")
                    self._draw_default_art()
                if s.artwork is not self._bg_art:
                    self._bg_art = s.artwork
                    try:
                        self._draw_bg(s.artwork)
                    except Exception as exc:
                        self._log.warning(f"draw_bg: {exc}")
            self._cv.tag_raise("art")
            self._draw_transport()
            return

        if self._last_art is not None:
            self._last_art = None
            self._draw_default_art()
        if self._bg_art is not None:
            self._bg_art = None
            self._draw_bg(None)
        self._draw_transport()

    # ── Notify Update ───────────────────────────────
    def notify_update(self, result):
        # show tray notification or popup
        print("Update available:", result)

    # ── Tick (50ms animation + dirty-flag poll) ───────────────────────────────
    def _tick(self) -> None:
        if self._state.consume_dirty():
            self._refresh()

        self._tick_count += 1
        if self._tick_count >= 600:   # ~30s
            self._tick_count = 0
            gc.collect()

        self._pulse += 0.06
        t = (math.sin(self._pulse) + 1) / 2
        T = self._theme
        if self._state.playing:
            col  = _blend(T["accent"], T["teal"], t)
            dash = (5, 6) if t > 0.5 else (2, 10)
        else:
            col  = T["border"]; dash = (2, 14)
        self._cv.itemconfig(self._ring, outline=col, dash=dash)

        # Title scroll
        title = self._title_str
        if title and self._title_item:
            W     = self.W
            avail = W - 32
            bbox  = self._cv.bbox(self._title_item)
            tw    = (bbox[2] - bbox[0]) if bbox else 0
            if tw > avail:
                overflow = tw - avail
                if self._title_pause > 0:
                    self._title_pause -= 1
                else:
                    self._title_off += 1.2 * self._title_dir
                    if self._title_off >= overflow:
                        self._title_off = overflow; self._title_dir = -1
                        self._title_pause = 80
                    elif self._title_off <= 0:
                        self._title_off = 0; self._title_dir = 1
                        self._title_pause = 80
                cx = W // 2 - int(self._title_off - overflow / 2)
            else:
                cx = W // 2
            self._cv.coords(self._title_item, cx, self._title_y)

        self._pulse_id = self.root.after(50, self._tick)

    # ── Volume ────────────────────────────────────────────────────────────────
    def _on_vol(self, val: int) -> None:
        self._audio._vol = max(0.0, min(1.0, val / 100.0))
        self._state.volume = val
        self._config["volume"] = val
        self._cv.itemconfig("vol_pct", text=f"{val}%")
        if self._vol_timer:
            try: self.root.after_cancel(self._vol_timer)
            except Exception: pass
        self._vol_timer = self.root.after(
            500, lambda: self._dacp.set_volume(val)
                         if self._state.active_remote else None)

    # ── Play/pause ────────────────────────────────────────────────────────────
    def _play_pause(self) -> None:
        if self._state.playing:
            self._audio.clear()
            self._state.playing = False
        else:
            self._state.playing = True
        self._state.mark_dirty()
        threading.Thread(target=self._dacp.play_pause, daemon=True).start()

    # ── Retheme ───────────────────────────────────────────────────────────────
    def retheme(self) -> None:
        T = self._theme
        self.root.configure(bg=T["bg"])
        self._cv.configure(bg=T["bg"])
        self._draw_bg(self._bg_art)
        self._tb.configure(bg=T["tbarbg"])
        self._tb_accent.configure(bg=T["accent"])
        self._tb_lbl.configure(bg=T["tbarbg"], fg=T["muted"])
        self._tb_xl.configure(bg=T["tbarbg"],  fg=T["muted"])
        self._tb_ml.configure(bg=T["tbarbg"],  fg=T["muted"])
        self._cv.itemconfig(self._codec_item, fill=T["teal"])
        self._cv.itemconfig(self._title_item, fill=T["text"])
        self._cv.itemconfig(self._info_item,  fill=T["muted"])
        self._cv.itemconfig("vol_lbl",  fill=T["teal"])
        self._cv.itemconfig("vol_pct",  fill=T["text2"])
        self._cv.itemconfig("devl",     fill=T["muted"])
        self._cv.itemconfig("gear_btn", fill=T["muted"])
        self._cv.itemconfig(self._div1, fill=T["border"])
        self._cv.itemconfig(self._div2, fill=T["border"])
        self._cv.itemconfig(self._ring, outline=T["accent"])
        self._vol_slider.update_theme(dict(T._t))
        self._draw_transport()
        if not self._state.artwork:
            self._draw_default_art()

    # ── Window controls ───────────────────────────────────────────────────────
    def show(self) -> None:
        self.root.deiconify(); self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    def hide(self) -> None:
        self.root.withdraw()

    def quit_app(self) -> None:
        if self._pulse_id:
            try: self.root.after_cancel(self._pulse_id)
            except Exception: pass
        self.root.quit()
