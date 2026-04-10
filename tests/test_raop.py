"""Tests for RAOP protocol helpers."""
import struct


def test_timing_reply_length():
    from airplay_receiver.raop import _timing_reply
    # Craft a valid 32-byte timing packet
    pkt = bytes(32)
    reply = _timing_reply(pkt)
    assert len(reply) == 32


def test_timing_reply_short_packet():
    from airplay_receiver.raop import _timing_reply
    assert _timing_reply(b"\x00" * 10) == b""


def test_find_free_tcp():
    from airplay_receiver.raop import find_free_tcp
    port = find_free_tcp(17000)   # use high port unlikely to conflict
    assert 17000 <= port < 17020


def test_device_id_format():
    from airplay_receiver.raop import _device_id
    did = _device_id()
    parts = did.split(":")
    assert len(parts) == 6
    for p in parts:
        assert len(p) == 2
        int(p, 16)   # must be valid hex


def test_alac_decoder_from_fmtp():
    from airplay_receiver.audio import AlacDecoder
    d = AlacDecoder.from_fmtp("a=fmtp:96 352 0 16 40 10 14 2 255 0 0 44100")
    assert d.channels == 2


def test_alac_decoder_from_fmtp_bad():
    from airplay_receiver.audio import AlacDecoder
    d = AlacDecoder.from_fmtp("garbage")
    # Should return a default decoder without crashing
    assert isinstance(d, AlacDecoder)
