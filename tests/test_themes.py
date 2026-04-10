"""Tests for theme system."""
import json
import tempfile
from pathlib import Path


def test_builtin_themes_have_required_keys():
    from airplay_receiver.themes import BUILT_IN, REQUIRED_KEYS
    for name, theme in BUILT_IN.items():
        missing = REQUIRED_KEYS - set(theme.keys())
        assert not missing, f"Theme '{name}' missing keys: {missing}"


def test_theme_manager_apply():
    from airplay_receiver.themes import ThemeManager
    with tempfile.TemporaryDirectory() as d:
        tm = ThemeManager(Path(d) / "t.json")
        for name in tm.names():
            tm.apply(name)
            assert tm["bg"]     # non-empty string
            assert tm["accent"]


def test_theme_manager_custom():
    from airplay_receiver.themes import ThemeManager, REQUIRED_KEYS
    with tempfile.TemporaryDirectory() as d:
        tf = Path(d) / "t.json"
        custom = {k: "#aabbcc" for k in REQUIRED_KEYS}
        custom["input_bg"] = "#000000"
        custom["input_fg"] = "#ffffff"
        tf.write_text(json.dumps({"My Custom": custom}))
        tm = ThemeManager(tf)
        assert "My Custom" in tm.names()
        tm.apply("My Custom")
        assert tm["bg"] == "#aabbcc"


def test_theme_fallback_unknown():
    from airplay_receiver.themes import ThemeManager
    with tempfile.TemporaryDirectory() as d:
        tm = ThemeManager(Path(d) / "t.json")
        tm.apply("Does Not Exist")   # should fall back to Indigo Night
        assert tm["accent"] == "#8b5cf6"


def test_colours_rgb():
    from airplay_receiver.ui.colours import rgb
    assert rgb("#ff0000") == (255, 0, 0)
    assert rgb("#000")    == (0, 0, 0)
    assert rgb("white")   == (255, 255, 255)


def test_colours_blend():
    from airplay_receiver.ui.colours import blend
    result = blend("#000000", "#ffffff", 0.0)
    assert result == "#000000"
    result = blend("#000000", "#ffffff", 1.0)
    assert result == "#ffffff"
