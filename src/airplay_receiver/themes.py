"""
Theme system: built-in themes + user custom themes from JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Built-in themes ───────────────────────────────────────────────────────────
BUILT_IN: dict[str, dict] = {
    # Dark themes
    "Indigo Night": {
        "bg":"#100c1e","surface":"#18122e","card":"#1f1840","card2":"#261e4a",
        "border":"#352d5e","tbarbg":"#0a0817","accent":"#8b5cf6","accent2":"#f05252",
        "teal":"#14b8a6","amber":"#f59e0b","text":"#f1f5f9","text2":"#c7c5e0",
        "muted":"#7470a0","green":"#10b981","input_bg":"#1f1840","input_fg":"#f1f5f9",
    },
    "Midnight Blue": {
        "bg":"#0a0f1e","surface":"#0f1830","card":"#162040","card2":"#1e2d55",
        "border":"#2a3d70","tbarbg":"#060c18","accent":"#3b82f6","accent2":"#f472b6",
        "teal":"#06b6d4","amber":"#fbbf24","text":"#e2e8f0","text2":"#94a3b8",
        "muted":"#475569","green":"#34d399","input_bg":"#162040","input_fg":"#e2e8f0",
    },
    "Dark Rose": {
        "bg":"#1a0a12","surface":"#2a0f1c","card":"#38102a","card2":"#4a1535",
        "border":"#6b1f4a","tbarbg":"#0f060c","accent":"#ec4899","accent2":"#f97316",
        "teal":"#14b8a6","amber":"#fbbf24","text":"#fce7f3","text2":"#fbcfe8",
        "muted":"#9d4e78","green":"#34d399","input_bg":"#38102a","input_fg":"#fce7f3",
    },
    "Forest": {
        "bg":"#0a130d","surface":"#0f1f14","card":"#142a1a","card2":"#1a3522",
        "border":"#254d30","tbarbg":"#060d08","accent":"#22c55e","accent2":"#84cc16",
        "teal":"#14b8a6","amber":"#f59e0b","text":"#f0fdf4","text2":"#bbf7d0",
        "muted":"#4ade80","green":"#22c55e","input_bg":"#142a1a","input_fg":"#f0fdf4",
    },
    "Ocean": {
        "bg":"#020b18","surface":"#051a30","card":"#082644","card2":"#0d3660",
        "border":"#1a5080","tbarbg":"#010810","accent":"#0ea5e9","accent2":"#38bdf8",
        "teal":"#22d3ee","amber":"#fbbf24","text":"#e0f2fe","text2":"#7dd3fc",
        "muted":"#0369a1","green":"#34d399","input_bg":"#082644","input_fg":"#e0f2fe",
    },
    # Light themes
    "Cloud Light": {
        "bg":"#f8fafc","surface":"#f1f5f9","card":"#e8eef5","card2":"#dde6f0",
        "border":"#cbd5e1","tbarbg":"#e2e8f0","accent":"#6366f1","accent2":"#ec4899",
        "teal":"#0891b2","amber":"#d97706","text":"#0f172a","text2":"#334155",
        "muted":"#64748b","green":"#059669","input_bg":"#ffffff","input_fg":"#0f172a",
    },
    "Warm Paper": {
        "bg":"#faf7f2","surface":"#f5f0e8","card":"#ede7d9","card2":"#e4dccb",
        "border":"#c8b89a","tbarbg":"#ede7d9","accent":"#b45309","accent2":"#dc2626",
        "teal":"#0f766e","amber":"#d97706","text":"#1c1917","text2":"#44403c",
        "muted":"#78716c","green":"#16a34a","input_bg":"#fffbf5","input_fg":"#1c1917",
    },
    "Arctic": {
        "bg":"#f0f7ff","surface":"#e6f0fb","card":"#d8e8f7","card2":"#c8ddf3",
        "border":"#93c5fd","tbarbg":"#daeafa","accent":"#2563eb","accent2":"#7c3aed",
        "teal":"#0891b2","amber":"#d97706","text":"#1e3a5f","text2":"#2563eb",
        "muted":"#64748b","green":"#059669","input_bg":"#ffffff","input_fg":"#1e3a5f",
    },
}

REQUIRED_KEYS = {
    "bg","surface","card","card2","border","tbarbg",
    "accent","accent2","teal","amber","text","text2","muted","green",
}


def load_themes(theme_file: Path) -> dict[str, dict]:
    """Merge built-ins with any user themes from theme_file."""
    themes: dict[str, dict] = dict(BUILT_IN)
    try:
        if theme_file.exists():
            user = json.loads(theme_file.read_text())
            for name, data in user.items():
                if isinstance(data, dict) and REQUIRED_KEYS.issubset(data.keys()):
                    themes[name] = data
    except Exception:
        pass
    return themes


def write_default_theme_file(theme_file: Path) -> None:
    """Write example theme file if it doesn't exist yet."""
    if theme_file.exists():
        return
    example = {
        "_readme": (
            "Add custom themes here. Required keys: "
            + ", ".join(sorted(REQUIRED_KEYS))
            + ", input_bg, input_fg"
        ),
        "GitHub Dark": {
            "bg":"#0d1117","surface":"#161b22","card":"#21262d","card2":"#30363d",
            "border":"#444c56","tbarbg":"#090c10","accent":"#58a6ff","accent2":"#ff7b72",
            "teal":"#39d353","amber":"#e3b341","text":"#c9d1d9","text2":"#8b949e",
            "muted":"#484f58","green":"#3fb950","input_bg":"#161b22","input_fg":"#c9d1d9",
        },
    }
    try:
        theme_file.write_text(json.dumps(example, indent=2))
    except Exception:
        pass


class ThemeManager:
    """Manages the active theme and exposes colour values."""

    def __init__(self, theme_file: Path) -> None:
        self._file    = theme_file
        self._themes  = load_themes(theme_file)
        self._current = "Indigo Night"
        self._t: dict = dict(BUILT_IN["Indigo Night"])

    def apply(self, name: str) -> None:
        self._themes  = load_themes(self._file)   # reload to pick up edits
        base = dict(BUILT_IN["Indigo Night"])      # fill in any missing keys
        base.update(self._themes.get(name, BUILT_IN["Indigo Night"]))
        if "input_bg" not in base: base["input_bg"] = base["card"]
        if "input_fg" not in base: base["input_fg"] = base["text"]
        self._current = name
        self._t = base

    def names(self) -> list[str]:
        self._themes = load_themes(self._file)
        return list(self._themes.keys())

    def __getitem__(self, key: str) -> str:
        return self._t[key]

    def get(self, key: str, default: str = "") -> str:
        return self._t.get(key, default)

    @property
    def current(self) -> str:
        return self._current
