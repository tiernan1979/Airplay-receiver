#!/usr/bin/env bash
set -e
BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      AirPlay Receiver — Linux Installer  ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/airplay-receiver"

if [[ ! -f "$BINARY" ]]; then
    echo "Error: airplay-receiver binary not found in $SCRIPT_DIR"
    exit 1
fi

# Install to /usr/local/bin
echo -e "[→] Installing binary to /usr/local/bin/airplay-receiver"
sudo install -m 755 "$BINARY" /usr/local/bin/airplay-receiver
echo -e "${GREEN}[✓] Binary installed${NC}"

# Create data directory
sudo mkdir -p /var/lib/airplay-receiver
sudo chmod 777 /var/lib/airplay-receiver
echo -e "${GREEN}[✓] Data dir: /var/lib/airplay-receiver${NC}"

# Firewall (ufw)
if command -v ufw &>/dev/null; then
    sudo ufw allow 7000:7020/tcp  comment "AirPlay Receiver" 2>/dev/null || true
    sudo ufw allow 6001:6050/udp  comment "AirPlay Receiver" 2>/dev/null || true
    sudo ufw allow 5353/udp       comment "mDNS"             2>/dev/null || true
    echo -e "${GREEN}[✓] UFW rules added${NC}"
fi

# Systemd user service (optional)
echo ""
read -p "  [?] Install systemd user service (auto-start on login)? [y/N] " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$HOME/.config/systemd/user/airplay-receiver.service" << SERVICE
[Unit]
Description=AirPlay Receiver
After=network.target sound.target graphical-session.target

[Service]
Type=simple
ExecStart=/usr/local/bin/airplay-receiver
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=default.target
SERVICE
    systemctl --user daemon-reload
    systemctl --user enable airplay-receiver
    echo -e "${GREEN}[✓] Systemd service installed and enabled${NC}"
    echo -e "    Run: ${BOLD}systemctl --user start airplay-receiver${NC}"
fi

# Desktop entry
echo ""
read -p "  [?] Create application menu entry? [y/N] " ans2
if [[ "$ans2" =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/airplay-receiver.desktop" << DESKTOP
[Desktop Entry]
Name=AirPlay Receiver
Comment=Receive AirPlay audio from Music Assistant
Exec=/usr/local/bin/airplay-receiver
Icon=multimedia-player
Terminal=false
Type=Application
Categories=AudioVideo;Audio;
StartupNotify=false
DESKTOP
    echo -e "${GREEN}[✓] Application menu entry created${NC}"
fi

echo ""
echo -e "${BOLD}Installation complete!${NC}"
echo -e "  Binary : /usr/local/bin/airplay-receiver"
echo -e "  Data   : /var/lib/airplay-receiver"
echo -e "  Config : /var/lib/airplay-receiver/config.json"
echo -e "  Log    : /var/lib/airplay-receiver/airplay_receiver.log"
echo ""
echo -e "  Launch: ${BOLD}airplay-receiver${NC}"
