"""
RAOP (Remote Audio Output Protocol) server — AirPlay 1 / cliraop compatible.

Handles the full RTSP handshake, three UDP sockets (data/control/timing),
NTP timing replies, and decodes ALAC audio frames into the AudioEngine.
"""
from __future__ import annotations

import hashlib
import io
import random
import socket
import struct
import threading
import time
from typing import TYPE_CHECKING

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .audio import AlacDecoder, AudioEngine
from .dacp  import DacpDiscovery, DacpRemote

if TYPE_CHECKING:
    from .config import Config, PlayerState

NTP_DELTA = 2208988800


def _device_id() -> str:
    h = hashlib.sha256(socket.gethostname().encode()).hexdigest()
    return ":".join(h[i:i+2] for i in range(0, 12, 2))


def _timing_reply(pkt: bytes) -> bytes:
    if len(pkt) < 32:
        return b""
    t   = time.time() + NTP_DELTA
    sec = int(t); frac = int((t - sec) * (2**32))
    ts  = struct.pack(">II", sec, frac)
    return bytes([0x80, 0xD3, pkt[2], pkt[3], 0, 0, 0, 0]) + pkt[24:32] + ts + ts


def _bind_free_udp(start: int = 6001, count: int = 80) -> tuple[socket.socket, int]:
    for port in range(start, start + count):
        try:
            import os
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            HOST = os.getenv("AIRPLAY_BIND", "0.0.0.0")
            s.bind((HOST, port))
            return s, port
        except OSError:
            pass
    raise RuntimeError("No free UDP port available")


def find_free_tcp(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))  # nosec B104
                return port
        except OSError:
            pass
    raise RuntimeError("No free TCP port available")


# ── RAOP Session ──────────────────────────────────────────────────────────────
class RaopSession:
    """One AirPlay connection from a sender."""

    def __init__(
        self,
        conn: socket.socket,
        addr: tuple,
        state: "PlayerState",
        config: "Config",
        audio: AudioEngine,
        dacp: DacpRemote,
    ) -> None:
        import logging
        self._log    = logging.getLogger("AirPlay")
        self.conn    = conn
        self.addr    = addr
        self._state  = state
        self._config = config
        self._audio  = audio
        self._dacp   = dacp
        self._active = True
        self._session   = str(random.randint(10000, 99999))
        self._rtp_seq   = random.randint(0, 0xFFFF)
        self._rtp_ts    = random.randint(0, 0xFFFFFFFF)
        self._sock_data = self._sock_ctrl = self._sock_time = None
        self._port_data = self._port_ctrl = self._port_time = 0
        self._alac: AlacDecoder | None = None
        self._codec_name = ""
        self._plog = 0

    def run(self) -> None:
        self._state.update(
            connected=True, client_ip=self.addr[0], playing=False,
            title="", artist="", album="", artwork=None,
        )
        try:
            buf = b""
            while self._active:
                chunk = self.conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\r\n\r\n" in buf:
                    header, _, rest = buf.partition(b"\r\n\r\n")
                    lines  = header.decode(errors="replace").splitlines()
                    first  = lines[0] if lines else ""
                    hdrs   = {}
                    for line in lines[1:]:
                        if ":" in line:
                            k, _, v = line.partition(":")
                            hdrs[k.strip().lower()] = v.strip()
                    clen   = int(hdrs.get("content-length", 0))
                    if len(rest) < clen:
                        break
                    body = rest[:clen]
                    buf  = rest[clen:]
                    self._handle(first, hdrs, body)
        except Exception as exc:
            if self._active:
                self._log.debug(f"Session: {exc}")
        finally:
            self._active = False
            self._state.update(
                connected=False, playing=False,
                title="", artist="", album="", artwork=None,
                dacp_id="", active_remote="",
            )
            try: self.conn.close()
            except Exception: pass

    def _handle(self, first: str, hdrs: dict, body: bytes) -> None:
        # Detect HTTP vs RTSP
        if first.startswith("GET ") or first.startswith("POST "):
            self._http(first, hdrs, body)
            return
        parts = first.split()
        if len(parts) < 2:
            return
        method = parts[0].upper()
        url    = parts[1]
        cseq   = hdrs.get("cseq", "0")
        self._log.debug(f"↑ {method} CSeq={cseq}")

        if method == "OPTIONS":
            self._options(hdrs, cseq)
        elif method == "ANNOUNCE":
            self._ann(body, cseq)
        elif method == "SETUP":
            self._setup(hdrs, cseq)
        elif method == "RECORD":
            self._record(cseq)
        elif method == "SET_PARAMETER":
            self._setparam(body, hdrs, cseq)
        elif method == "GET_PARAMETER":
            self._getparam(cseq)
        elif method == "FLUSH":
            self._flush(cseq)
        elif method == "TEARDOWN":
            self._teardown(cseq)
        else:
            self._rtsp_send(cseq=cseq)

    # ── RTSP response helpers ─────────────────────────────────────────────────
    def _rtsp_send(
        self,
        status: int = 200,
        cseq: str = "0",
        extra: dict | None = None,
        body: bytes = b"",
    ) -> None:
        lines = [f"RTSP/1.0 {status} {'OK' if status == 200 else 'Error'}",
                 f"CSeq: {cseq}",
                 "Server: AirPlayReceiver/11.0",
                 "Audio-Jack-Status: connected; type=digital"]
        if extra:
            for k, v in extra.items():
                lines.append(f"{k}: {v}")
        if body:
            lines.append(f"Content-Length: {len(body)}")
        lines.append("\r\n")
        try:
            self.conn.sendall(("\r\n".join(lines)).encode() + body)
        except Exception as exc:
            self._log.debug(f"RTSP send: {exc}")

    def _http(self, first: str, hdrs: dict, body: bytes) -> None:
        self._log.debug(f"HTTP {first[:60]}")
        self.conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")

    # ── RTSP method handlers ──────────────────────────────────────────────────
    def _options(self, hdrs: dict, cseq: str) -> None:
        did = hdrs.get("dacp-id", "")
        ar  = hdrs.get("active-remote", "")
        if did and ar:
            self._state.update(dacp_id=did, active_remote=ar)
            self._log.warning(f"DACP id={did} remote={ar}")
        self._rtsp_send(
            cseq=cseq,
            extra={
                "Public": (
                    "ANNOUNCE, SETUP, RECORD, PAUSE, FLUSH, TEARDOWN, "
                    "OPTIONS, GET_PARAMETER, SET_PARAMETER"
                )
            },
        )

    def _ann(self, body: bytes, cseq: str) -> None:
        sdp  = body.decode(errors="replace")
        fmtp = ""
        for line in sdp.splitlines():
            line = line.strip()
            if line.startswith("a=rtpmap:"):
                rest = line.split(":", 1)[1].split(None, 1)
                if len(rest) >= 2:
                    self._codec_name = rest[1].split("/")[0].upper()
            if line.startswith("a=fmtp:"):
                fmtp = line
        if "APPLELOSSLESS" in self._codec_name or "ALAC" in self._codec_name:
            self._alac = AlacDecoder.from_fmtp(fmtp) if fmtp else AlacDecoder()
            self._state.update(codec="ALAC")
        else:
            self._alac = None
            self._state.update(codec=self._codec_name or "PCM")
        self._rtsp_send(cseq=cseq)

    def _setup(self, hdrs: dict, cseq: str) -> None:
        t = hdrs.get("transport", "")
        self._log.debug(f"SETUP: {t}")
        self._sock_data, self._port_data = _bind_free_udp(6001)
        self._sock_ctrl, self._port_ctrl = _bind_free_udp(self._port_data + 1)
        self._sock_time, self._port_time = _bind_free_udp(self._port_ctrl + 1)
        for s in (self._sock_data, self._sock_ctrl, self._sock_time):
            s.settimeout(1.0)
        threading.Thread(target=self._rtp,    daemon=True).start()
        threading.Thread(target=self._ctrl,   daemon=True).start()
        threading.Thread(target=self._timing, daemon=True).start()
        self._rtsp_send(
            cseq=cseq,
            extra={
                "Transport": (
                    f"RTP/AVP/UDP;unicast;mode=record;"
                    f"server_port={self._port_data};"
                    f"control_port={self._port_ctrl};"
                    f"timing_port={self._port_time}"
                ),
                "Session": f"{self._session};timeout=60",
                "Audio-Jack-Status": "connected; type=digital",
            },
        )

    def _record(self, cseq: str) -> None:
        self._state.playing = True
        self._state.mark_dirty()
        self._rtsp_send(
            cseq=cseq,
            extra={
                "Audio-Latency": "11025",
                "RTP-Info": f"seq={self._rtp_seq};rtptime={self._rtp_ts}",
            },
        )

    def _setparam(self, body: bytes, hdrs: dict, cseq: str) -> None:
        ct = hdrs.get("content-type", "")
        if "x-dmap-tagged" in ct:
            self._dmap(body)
        elif "image/" in ct:
            self._art(body)
        elif "text/parameters" in ct:
            for line in body.decode(errors="replace").splitlines():
                if line.startswith("volume:"):
                    try:
                        raw = float(line.split(":", 1)[1].strip())
                        if raw < -40.0:
                            pass  # ignore probe/mute
                        else:
                            pct = max(5, min(100, int((raw + 30) / 30 * 100)))
                            self._audio.set_volume(pct)
                            self._config["volume"] = pct
                            self._state.volume = pct
                            self._state.mark_dirty()
                            self._log.warning(f"Volume: {raw:.1f}dB → {pct}%")
                    except Exception:
                        pass
        self._rtsp_send(cseq=cseq)

    def _getparam(self, cseq: str) -> None:
        vol = self._state.volume
        db  = -30.0 + (vol / 100.0) * 30.0
        self._rtsp_send(
            cseq=cseq,
            extra={"Content-Type": "text/parameters"},
            body=f"volume: {db:.4f}\r\n".encode(),
        )

    def _flush(self, cseq: str) -> None:
        self._audio.clear()
        self._state.playing = False
        self._state.mark_dirty()
        self._log.warning("MA → Paused")
        self._rtsp_send(cseq=cseq)

    def _teardown(self, cseq: str) -> None:
        self._rtsp_send(cseq=cseq)
        self._active = False

    # ── UDP threads ───────────────────────────────────────────────────────────
    def _rtp(self) -> None:
        while self._active:
            try:
                pkt, _ = self._sock_data.recvfrom(2048)
                if len(pkt) < 12:
                    continue
                payload = pkt[12:]
                if self._alac:
                    pcm = self._alac.decode(payload)
                    if pcm:
                        self._audio.push(pcm)
                        if not self._state.playing:
                            self._state.update(playing=True)
            except socket.timeout:
                continue
            except Exception as exc:
                if self._active:
                    self._log.debug(f"RTP: {exc}")
                break

    def _ctrl(self) -> None:
        while self._active:
            try:
                self._sock_ctrl.recvfrom(512)
            except socket.timeout:
                continue
            except Exception:
                break

    def _timing(self) -> None:
        while self._active:
            try:
                pkt, addr = self._sock_time.recvfrom(128)
                reply = _timing_reply(pkt)
                if reply:
                    self._sock_time.sendto(reply, addr)
            except socket.timeout:
                continue
            except Exception as exc:
                if self._active:
                    self._log.debug(f"Timing: {exc}")
                break

    # ── Metadata helpers ──────────────────────────────────────────────────────
    def _dmap(self, data: bytes) -> None:
        meta: dict = {}
        i = 0
        while i + 8 <= len(data):
            tag  = data[i:i+4].decode(errors="replace")
            size = struct.unpack(">I", data[i+4:i+8])[0]
            val  = data[i+8:i+8+size]
            i   += 8 + size
            if tag in ("minm", "asar", "asal"):
                try:
                    meta[tag] = val.decode("utf-8", errors="replace")
                except Exception:
                    pass
        t  = meta.get("minm", "")
        a  = meta.get("asar", "")
        al = meta.get("asal", "")
        if t or a:
            self._state.update(title=t, artist=a, album=al)
            self._log.warning(f"Now playing: {t} – {a}")

    def _art(self, data: bytes) -> None:
        if not PIL_AVAILABLE or not data:
            return
        try:
            img = Image.open(io.BytesIO(data))
            img.thumbnail((300, 300), Image.BILINEAR)
            img = img.convert("RGBA")

            class _ArtWrapper:
                def __init__(self, im): self.im = im
                def convert(self, *a, **k): return self.im.convert(*a, **k)

            self._state.update(artwork=_ArtWrapper(img))
        except Exception as exc:
            self._log.debug(f"Art: {exc}")


# ── RAOP TCP Server ───────────────────────────────────────────────────────────
class RaopServer:
    def __init__(
        self,
        port: int,
        state: "PlayerState",
        config: "Config",
        audio: AudioEngine,
        dacp: DacpRemote,
    ) -> None:
        import logging
        self._log    = logging.getLogger("AirPlay")
        self.port    = port
        self._state  = state
        self._config = config
        self._audio  = audio
        self._dacp   = dacp
        self._sock: socket.socket | None = None

    def start(self) -> bool:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("0.0.0.0", self.port)) # nosec B104
        except OSError as exc:
            self._log.error(f"Bind {self.port}: {exc}")
            return False
        self._sock.listen(10)
        self._sock.settimeout(1.0)
        threading.Thread(target=self._loop, daemon=True, name="accept").start()
        self._log.warning(f"RAOP TCP {self.port}")
        return True

    def _loop(self) -> None:
        while True:
            try:
                conn, addr = self._sock.accept()
                session = RaopSession(
                    conn, addr,
                    self._state, self._config,
                    self._audio, self._dacp,
                )
                threading.Thread(
                    target=session.run, daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception as exc:
                self._log.error(f"Accept: {exc}")
                break

    def stop(self) -> None:
        if self._sock:
            try: self._sock.close()
            except Exception: pass


# ── mDNS Advertiser ───────────────────────────────────────────────────────────
class MdnsAdvertiser:
    RAOP_TYPE = "_raop._tcp.local."

    def __init__(self, name: str, port: int) -> None:
        import logging
        self._log  = logging.getLogger("AirPlay")
        self.name  = name
        self.port  = port
        self._zc   = None

    def _local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self) -> None:
        try:
            from zeroconf import ServiceInfo, Zeroconf
            ip    = self._local_ip()
            ip_b  = socket.inet_aton(ip)
            mac   = _device_id().replace(":", "")
            props = {
                b"txtvers": b"1", b"ch": b"2", b"cn": b"0,1",
                b"et": b"0",      b"sv": b"false", b"da": b"true",
                b"sr": b"44100",  b"ss": b"16",    b"pw": b"false",
                b"vn": b"65537",  b"tp": b"UDP",   b"md": b"0,1,2",
                b"am": b"AirPort10,115", b"vs": b"366.0",
            }
            self._zc  = Zeroconf(interfaces=[ip])
            hn        = f"{socket.gethostname()}.local."
            self._svc = ServiceInfo(
                self.RAOP_TYPE,
                f"{mac}@{self.name}.{self.RAOP_TYPE}",
                addresses=[ip_b],
                port=self.port,
                properties=props,
                server=hn,
            )
            self._zc.register_service(self._svc)
            self._log.warning(f"mDNS: '{mac}@{self.name}' @ {ip}:{self.port}")
        except Exception as exc:
            self._log.error(f"mDNS: {exc}")

    def stop(self) -> None:
        if self._zc:
            try:
                self._zc.unregister_all_services()
                self._zc.close()
            except Exception:
                pass
