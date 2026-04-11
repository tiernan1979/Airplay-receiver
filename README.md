# AirPlay Receiver

[![CI](https://github.com/YOUR_USERNAME/airplay-receiver/actions/workflows/ci.yml/badge.svg)](https://github.com/tiernan1979/airplay-receiver/actions)

Cross-platform AirPlay / RAOP audio receiver with a modern UI.
Built for use with **Music Assistant** (Home Assistant) but works with any AirPlay sender.

---

## Features

- 🎵 Receives AirPlay 1 / RAOP streams (Music Assistant, iTunes, etc.)
- 🔊 ALAC (Apple Lossless) decoding via PyAV / FFmpeg
- 🎨 8 built-in themes (5 dark, 3 light) + custom theme support
- 🖼️ Album art with blurred background bleed
- 🔄 Bidirectional play/pause/volume sync with Music Assistant (DACP)
- 📌 System tray — runs minimised, no taskbar entry
- 🪟 Windows 10/11 + 🐧 Linux (X11/Wayland)

---

## Quick Start

### Pre-built binaries (recommended)

Download from [Releases](https://github.com/YOUR_USERNAME/airplay-receiver/releases):

| Platform | File | Notes |
|----------|------|-------|
| Windows  | `AirPlayReceiver.msi` | Run install as Admin |
| Linux    | `AirPlayReceiver-Linux.tar.gz` | Run `./install.sh` |

### From source

**Requirements:** Python 3.10+

```bash
git clone https://github.com/tiernan1979/airplay-receiver
cd airplay-receiver
pip install -e .
airplay-receiver
```

---

## Installation

### Windows

1. Download `AirPlayReceiver.msi`
2. Run `AirPlayReceiver.msi` **as Administrator**
3. The installer:
   - Copies exe to `C:\Program FIles\AirPlayReceiver\`
   - Creates Start Menu shortcut
   - Optionally adds to Windows Startup
   - Adds Windows Firewall rules

### Linux

```bash
tar -xzf AirPlayReceiver-Linux.tar.gz
chmod +x install.sh
./install.sh
```

The installer optionally creates a **systemd user service** for auto-start on login.

**System dependencies** (Ubuntu/Debian):
```bash
sudo apt-get install python3-tk portaudio19-dev ffmpeg
```

---

## Music Assistant Setup

1. In Music Assistant → Settings → Players, your device appears as `AirPlay-<hostname>`
2. No pairing required — connects automatically
3. Recommended player settings:
   - Stereo output: ✅
   - Volume normalisation (EBU-R128): optional
   - Smart fades: optional

---

## Firewall Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 7000–7020 | TCP | RTSP control |
| 6001–6050 | UDP | RTP audio + NTP timing |
| 5353 | UDP | mDNS discovery |

---

## Data Locations

| Platform | Path |
|----------|------|
| Windows  | `C:\ProgramData\AirPlayReceiver\` |
| Linux    | `/var/lib/airplay-receiver/` (or `~/.local/share/airplay-receiver/`) |

Files: `config.json`, `themes.json`, `airplay_receiver.log`

---

## Custom Themes

Edit `themes.json` (Settings → Open Theme File):

```json
{
  "My Theme": {
    "bg":       "#0d1117",
    "surface":  "#161b22",
    "card":     "#21262d",
    "card2":    "#30363d",
    "border":   "#444c56",
    "tbarbg":   "#090c10",
    "accent":   "#58a6ff",
    "accent2":  "#ff7b72",
    "teal":     "#39d353",
    "amber":    "#e3b341",
    "text":     "#c9d1d9",
    "text2":    "#8b949e",
    "muted":    "#484f58",
    "green":    "#3fb950",
    "input_bg": "#161b22",
    "input_fg": "#c9d1d9"
  }
}
```

---

## Development

```bash
git clone https://github.com/tiernan1979E/airplay-receiver
cd airplay-receiver
pip install -e ".[dev]"
pytest tests/ -v
```

### Project structure

```
src/airplay_receiver/
├── __main__.py        Entry point
├── audio.py           AudioEngine + ALAC decoder
├── config.py          Config, PlayerState, logging
├── dacp.py            DACP remote control
├── platform.py        Cross-platform helpers
├── raop.py            RAOP/RTSP server + mDNS
├── themes.py          Theme system
└── ui/
    ├── buttons.py     Sphere button renderer
    ├── colours.py     Colour utilities
    ├── main_window.py Main UI window
    ├── settings.py    Settings dialog
    └── widgets.py     CanvasSlider, Marquee
```

### CI/CD

GitHub Actions runs on every push:
1. **Bandit** — static security analysis
2. **pip-audit** — dependency CVE scan
3. **pytest** — unit tests (Python 3.10, 3.11, 3.12)
4. **PyInstaller** — builds Windows EXE and Linux binary
5. On GitHub Release — binaries auto-uploaded as release assets

---

## Building

### Windows EXE
```bat
pip install pyinstaller
pyinstaller --onefile --noconsole --name AirPlayReceiver ^
  src/airplay_receiver/__main__.py
```

### Linux binary
```bash
pip install pyinstaller
pyinstaller --onefile --name airplay-receiver \
  src/airplay_receiver/__main__.py
```

---

## Troubleshooting

**No audio on first play** — pause and play once; volume sync initialises on first MA connection.

**Device not found in Music Assistant** — check firewall rules; ensure same network/VLAN.

**Robot voice / distorted audio** — check Settings → Audio Status for sample rate. If showing `↕ resampling`, the device native rate differs from 44100 Hz (normal, handled automatically).

**Log file** — Settings → Open Log File, or:
- Windows: `C:\ProgramData\AirPlayReceiver\airplay_receiver.log`
- Linux: `/var/lib/airplay-receiver/airplay_receiver.log`

Enable **Debug Logging** in Settings for verbose RTSP/DACP/RTP detail.

---

## License

MIT
