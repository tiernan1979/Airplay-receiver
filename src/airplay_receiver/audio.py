"""
Audio engine: ring-buffer playback, ALAC decoding, resampling.
"""
from __future__ import annotations

import struct
import threading
from typing import TYPE_CHECKING

import numpy as np

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False

try:
    import av as pyav
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False

if TYPE_CHECKING:
    from .config import PlayerState

SAMPLE_RATE = 44100
CHANNELS    = 2
CHUNK       = 1024   # sounddevice blocksize in frames


# ── ALAC Decoder ──────────────────────────────────────────────────────────────
class AlacDecoder:
    """Decode ALAC RTP payloads → int16 LE interleaved stereo PCM via PyAV."""

    def __init__(
        self,
        frame_len: int   = 352,
        compat_ver: int  = 0,
        bit_depth: int   = 16,
        rice_hist: int   = 40,
        rice_init: int   = 10,
        rice_limit: int  = 14,
        channels: int    = 2,
        max_run: int     = 255,
        max_frame: int   = 0,
        avg_bit: int     = 0,
        sample_rate: int = 44100,
    ) -> None:
        self.channels = channels
        self._ok      = False
        self._errs    = 0

        if not AV_AVAILABLE:
            return
        try:
            # Build ALACSpecificConfig (24 bytes) + 'alac' box (36 bytes total)
            alac_cfg = struct.pack(
                ">IBBBBBBHIII",
                frame_len, compat_ver, bit_depth,
                rice_hist, rice_init, rice_limit,
                channels, max_run, max_frame, avg_bit, sample_rate,
            )
            box = (
                struct.pack(">I", 36)
                + b"alac"
                + struct.pack(">I", 0)
                + alac_cfg
            )
            codec = pyav.CodecContext.create("alac", "r")
            codec.extradata = box
            codec.open()
            self._ctx = codec
            self._ok  = True
        except Exception as exc:
            import logging
            logging.getLogger("AirPlay").error(f"ALAC init: {exc}")

    def decode(self, data: bytes) -> bytes:
        """Return int16 LE interleaved stereo PCM, or b'' on error."""
        if not self._ok or not data:
            return b""
        try:
            pkt = pyav.Packet(data)
            out = b""
            for frame in self._ctx.decode(pkt):
                arr = frame.to_ndarray()

                if not hasattr(self, "_logged"):
                    self._logged = True
                    import logging
                    logging.getLogger("AirPlay").warning(
                        f"ALAC first frame: dtype={arr.dtype} "
                        f"shape={arr.shape} sr={frame.sample_rate}"
                    )

                if arr.dtype == np.int32:
                    arr = (arr >> 16).astype(np.int16)
                elif arr.dtype in (np.float32, np.float64):
                    arr = (arr * 32767.0).clip(-32768, 32767).astype(np.int16)
                elif arr.dtype != np.int16:
                    arr = arr.astype(np.int16)

                if arr.ndim == 2 and arr.shape[0] == self.channels:
                    arr = arr.T.reshape(-1)  # planar → interleaved
                elif arr.ndim == 2:
                    arr = arr.reshape(-1)

                out += arr.tobytes()

            if not out:
                if self._errs < 3:
                    import logging
                    logging.getLogger("AirPlay").warning(
                        f"ALAC 0 bytes for {len(data)}B payload"
                    )
                self._errs += 1
            return out

        except Exception as exc:
            if self._errs < 3:
                import logging
                logging.getLogger("AirPlay").error(f"ALAC decode: {exc}")
            self._errs += 1
            return b""

    @classmethod
    def from_fmtp(cls, fmtp: str) -> "AlacDecoder":
        """Parse SDP fmtp line: a=fmtp:96 352 0 16 40 10 14 2 255 0 0 44100"""
        try:
            s = fmtp.strip()
            if "fmtp:" in s:
                s = s.split("fmtp:", 1)[1]
            parts = s.split()
            nums  = [int(x) for x in parts[1:]]   # skip payload type
            if len(nums) >= 11:
                return cls(
                    frame_len=nums[0],   compat_ver=nums[1], bit_depth=nums[2],
                    rice_hist=nums[3],   rice_init=nums[4],  rice_limit=nums[5],
                    channels=nums[6],    max_run=nums[7],    max_frame=nums[8],
                    avg_bit=nums[9],     sample_rate=nums[10],
                )
        except Exception:
            pass
        return cls()


# ── Audio Engine ──────────────────────────────────────────────────────────────
class AudioEngine:
    """
    Ring-buffer audio playback.

    PCM is pushed from the ALAC decode thread; the sounddevice callback
    pulls exactly what it needs from the bytearray ring buffer.
    No queue.Queue → no per-frame allocations, no padding artefacts.
    """

    SRC_RATE = SAMPLE_RATE
    BUF_MAX  = SAMPLE_RATE * CHANNELS * 2 * 2   # 2 seconds of int16 stereo

    def __init__(self, initial_volume: int = 80, device=None) -> None:
        self.stream     = None
        self._running   = False
        self._vol       = max(0.0, min(1.0, initial_volume / 100.0))
        self._device    = device
        self._dst_rate  = self.SRC_RATE
        self._buf       = bytearray()
        self._lock      = threading.Lock()

    # ── Device helpers ────────────────────────────────────────────────────────
    def list_devices(self) -> list[tuple[int, str]]:
        if not AUDIO_AVAILABLE:
            return []
        try:
            return [
                (i, d["name"])
                for i, d in enumerate(sd.query_devices())
                if d["max_output_channels"] > 0
            ]
        except Exception:
            return []

    def _query_device_rate(self) -> int:
        if not AUDIO_AVAILABLE:
            return self.SRC_RATE
        try:
            dev = (
                sd.query_devices(self._device, "output")
                if self._device is not None
                else sd.query_devices(sd.default.device[1], "output")
            )
            rate = int(dev.get("default_samplerate", self.SRC_RATE))
            import logging
            logging.getLogger("AirPlay").warning(f"Audio device native rate: {rate} Hz")
            return rate
        except Exception as exc:
            import logging
            logging.getLogger("AirPlay").warning(
                f"Could not query device rate ({exc}), using {self.SRC_RATE}"
            )
            return self.SRC_RATE

    # ── Resampling ────────────────────────────────────────────────────────────
    @staticmethod
    def resample(data: bytes, src: int, dst: int) -> bytes:
        if src == dst:
            return data
        arr   = np.frombuffer(data, dtype="<i2").reshape(-1, 2).astype(np.float32)
        n_src = arr.shape[0]
        n_dst = int(round(n_src * dst / src))
        xs    = np.linspace(0, n_src - 1, n_src)
        xd    = np.linspace(0, n_src - 1, n_dst)
        out   = np.zeros((n_dst, 2), dtype=np.float32)
        out[:, 0] = np.interp(xd, xs, arr[:, 0])
        out[:, 1] = np.interp(xd, xs, arr[:, 1])
        return out.astype(np.int16).reshape(-1).tobytes()

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def start(self) -> None:
        if not AUDIO_AVAILABLE:
            return
        self._running  = True
        self._dst_rate = self._query_device_rate()
        with self._lock:
            self._buf.clear()
        try:
            kw: dict = dict(
                samplerate=self._dst_rate,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK,
                callback=self._cb,
            )
            if self._device is not None:
                kw["device"] = self._device
            self.stream = sd.OutputStream(**kw)
            self.stream.start()
            import logging
            logging.getLogger("AirPlay").warning(
                f"Audio: device={self._device} "
                f"src={self.SRC_RATE}Hz dst={self._dst_rate}Hz"
            )
        except Exception as exc:
            import logging
            logging.getLogger("AirPlay").error(f"Audio start: {exc}")

    def stop(self) -> None:
        self._running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def set_device(self, idx) -> None:
        self._device = idx
        if self._running:
            self.stop()
            self.start()

    # ── Volume ────────────────────────────────────────────────────────────────
    def set_volume(self, pct: int) -> None:
        self._vol = max(0.0, min(1.0, pct / 100.0))

    # ── Buffer ops ────────────────────────────────────────────────────────────
    def push(self, pcm: bytes) -> None:
        if not pcm:
            return
        if self._dst_rate != self.SRC_RATE:
            pcm = self.resample(pcm, self.SRC_RATE, self._dst_rate)
        with self._lock:
            self._buf.extend(pcm)
            if len(self._buf) > self.BUF_MAX:
                del self._buf[: len(self._buf) - self.BUF_MAX]

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    # ── sounddevice callback (runs in audio thread) ───────────────────────────
    def _cb(self, outdata, frames, t, status) -> None:
        need = frames * CHANNELS * 2  # bytes
        with self._lock:
            have = len(self._buf)
            if have >= need:
                chunk = bytes(self._buf[:need])
                del self._buf[:need]
            elif have > 0:
                chunk = bytes(self._buf) + bytes(need - have)
                self._buf.clear()
            else:
                chunk = None
        if chunk:
            arr = np.frombuffer(chunk, dtype="<i2").copy()
            outdata[:] = (arr * self._vol).astype(np.int16).reshape(-1, CHANNELS)
        else:
            outdata.fill(0)
