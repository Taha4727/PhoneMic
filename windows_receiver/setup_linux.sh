#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
AUTO_YES=0
SKIP_PKG=0

for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO_YES=1 ;;
        --skip-system-pkgs) SKIP_PKG=1 ;;
        -h|--help)
            cat <<'EOF'
PhoneMic Receiver Linux Setup

Usage: ./setup_linux.sh [--yes] [--skip-system-pkgs]

  --yes, -y            Install missing pacman packages without prompting
  --skip-system-pkgs   Skip OS package installation and only configure .venv + desktop launcher
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

echo "=== PhoneMic Receiver Linux Setup ==="

if [[ "$SKIP_PKG" -eq 0 ]]; then
    if command -v pacman >/dev/null 2>&1; then
        PKGS=(python portaudio tk pipewire-pulse)
        MISSING=()
        for p in "${PKGS[@]}"; do
            if ! pacman -Qi "$p" >/dev/null 2>&1; then
                MISSING+=("$p")
            fi
        done
        if [[ "${#MISSING[@]}" -gt 0 ]]; then
            echo "[*] Missing Arch packages: ${MISSING[*]}"
            if [[ "$AUTO_YES" -eq 1 ]]; then
                sudo pacman -S --needed --noconfirm "${MISSING[@]}"
            else
                sudo pacman -S --needed "${MISSING[@]}"
            fi
        else
            echo "[+] Core Arch system packages already installed (python, portaudio, tk, pipewire-pulse)."
        fi
        if ! command -v pavucontrol >/dev/null 2>&1; then
            echo "[i] Optional: install 'pavucontrol' or 'qpwgraph' for GUI PipeWire/PulseAudio routing."
        fi
    else
        echo "[!] Non-Arch system detected (pacman not found)."
        echo "    Ensure Python 3.8+, Tk, PortAudio dev/runtime libs, and pipewire-pulse/pulseaudio-utils are installed."
    fi
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "[!] python3 not found in PATH." >&2
    exit 1
fi

echo "[*] Creating virtual environment in $VENV_DIR (--system-site-packages)..."
python3 -m venv --system-site-packages "$VENV_DIR"

echo "[*] Installing Python dependencies from requirements.txt..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

chmod +x "$SCRIPT_DIR/start_receiver.sh" "$SCRIPT_DIR/linux/phonemic-receiver" "$SCRIPT_DIR/phonemic_receiver.py" "$SCRIPT_DIR/phonemic_cli.py"

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

ln -sf "$SCRIPT_DIR/linux/phonemic-receiver" "$BIN_DIR/phonemic-receiver"
if [[ -f "$SCRIPT_DIR/assets/phonemic.png" ]]; then
    cp -f "$SCRIPT_DIR/assets/phonemic.png" "$ICON_DIR/phonemic-receiver.png"
fi

# Install desktop entry with absolute launcher path so desktop menus work regardless of PATH
LAUNCHER_ABS="$SCRIPT_DIR/linux/phonemic-receiver"
sed "s|^Exec=.*|Exec=$LAUNCHER_ABS %U|" "$SCRIPT_DIR/linux/phonemic-receiver.desktop" \
    > "$APP_DIR/phonemic-receiver.desktop"
chmod 644 "$APP_DIR/phonemic-receiver.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "[+] Installed desktop entry: $APP_DIR/phonemic-receiver.desktop"
echo "[+] Linked CLI launcher:    $BIN_DIR/phonemic-receiver"

if command -v ufw >/dev/null 2>&1; then
    UFW_STATE="$(ufw status 2>/dev/null | head -n1 || true)"
    if [[ "$UFW_STATE" == *"active"* ]] && ! ufw status 2>/dev/null | grep -q "5001"; then
        echo "[!] UFW is active and port 5001 is not open. Allow PhoneMic with:"
        echo "    sudo ufw allow 5001/udp && sudo ufw allow 5001/tcp"
    fi
elif command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld 2>/dev/null; then
    if ! firewall-cmd --list-ports 2>/dev/null | grep -q "5001"; then
        echo "[!] firewalld is active and port 5001 is not open. Allow PhoneMic with:"
        echo "    sudo firewall-cmd --add-port=5001/udp --add-port=5001/tcp --permanent && sudo firewall-cmd --reload"
    fi
fi

echo "[*] Running environment check..."
"$VENV_DIR/bin/python" "$SCRIPT_DIR/phonemic_receiver.py" --check || true
echo ""
echo "Setup complete. Launch via application menu ('PhoneMic Receiver') or:"
echo "  $SCRIPT_DIR/start_receiver.sh"
