"""
Unit tests for audio engine — no real audio device needed.
"""
import pytest
import numpy as np


def test_resample_passthrough():
    from airplay_receiver.audio import AudioEngine
    data = bytes(range(256))
    assert AudioEngine.resample(data, 44100, 44100) == data


def test_resample_changes_length():
    from airplay_receiver.audio import AudioEngine
    # 100 stereo int16 frames at 44100 → 48000
    arr   = np.zeros((100, 2), dtype=np.int16)
    data  = arr.tobytes()
    out   = AudioEngine.resample(data, 44100, 48000)
    n_out = len(out) // 4  # 4 bytes per stereo int16 frame
    expected = round(100 * 48000 / 44100)
    assert abs(n_out - expected) <= 1


def test_buffer_cap():
    """Ring buffer should never exceed BUF_MAX bytes."""
    from airplay_receiver.audio import AudioEngine
    audio = AudioEngine(initial_volume=50)
    chunk = bytes(1024)
    for _ in range(1000):
        audio.push(chunk)
    with audio._lock:
        assert len(audio._buf) <= audio.BUF_MAX


def test_clear():
    from airplay_receiver.audio import AudioEngine
    audio = AudioEngine()
    audio._buf.extend(b"\x00" * 4096)
    audio.clear()
    with audio._lock:
        assert len(audio._buf) == 0


def test_volume_range():
    from airplay_receiver.audio import AudioEngine
    audio = AudioEngine()
    audio.set_volume(0)
    assert audio._vol == 0.0
    audio.set_volume(100)
    assert audio._vol == 1.0
    audio.set_volume(150)
    assert audio._vol == 1.0
    audio.set_volume(-10)
    assert audio._vol == 0.0
