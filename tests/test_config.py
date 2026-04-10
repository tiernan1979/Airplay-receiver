"""Tests for Config and PlayerState."""
import json
import tempfile
from pathlib import Path
import pytest


def test_config_defaults():
    from airplay_receiver.config import Config
    with tempfile.TemporaryDirectory() as d:
        cfg = Config(Path(d) / "config.json")
        assert cfg["volume"] == 80
        assert cfg["theme"] == "Indigo Night"


def test_config_save_load():
    from airplay_receiver.config import Config
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "config.json"
        cfg = Config(p)
        cfg["volume"] = 42
        cfg2 = Config(p)
        assert cfg2["volume"] == 42


def test_state_dirty_flag():
    from airplay_receiver.config import PlayerState
    s = PlayerState()
    assert not s.consume_dirty()
    s.update(playing=True)
    assert s.consume_dirty()
    assert not s.consume_dirty()


def test_state_mark_dirty():
    from airplay_receiver.config import PlayerState
    s = PlayerState()
    s.playing = True
    assert not s.consume_dirty()   # direct assignment doesn't set flag
    s.mark_dirty()
    assert s.consume_dirty()


def test_state_on_change():
    from airplay_receiver.config import PlayerState
    s = PlayerState()
    fired = []
    s.on_change(lambda: fired.append(1))
    s.update(title="Hello")
    assert len(fired) == 1
    s.update(title="Hello")   # same value — no change
    assert len(fired) == 1
