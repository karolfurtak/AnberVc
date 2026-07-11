#!/bin/bash
# AnberVc installer dla Anbernic RG40XX V
# Uruchom jako root na konsoli (przez SSH lub terminal)
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APPS_DIR="/mnt/mmc/Roms/APPS"
APP_DIR="$APPS_DIR/anbervc"
IMGS_DIR="$APPS_DIR/Imgs"

echo "=== AnberVc install ==="

# 1. App (main.py + vc_lib + power_screen) + launcher
mkdir -p "$APP_DIR/app" "$APP_DIR/vc_lib"
cp "$REPO_DIR/app/main.py"         "$APP_DIR/app/main.py"
cp "$REPO_DIR/app/power_screen.py" "$APP_DIR/app/power_screen.py"
cp "$REPO_DIR/vc_lib/"*.py         "$APP_DIR/vc_lib/"
cp "$REPO_DIR/app/AnberVc.sh"      "$APPS_DIR/AnberVc.sh"
chmod +x "$APPS_DIR/AnberVc.sh"
echo "OK: app w $APP_DIR"

# 2. Ikona
mkdir -p "$IMGS_DIR"
if [ -f "$REPO_DIR/AnberVc.png" ]; then
    cp "$REPO_DIR/AnberVc.png" "$IMGS_DIR/AnberVc.png"
    echo "OK: ikona w $IMGS_DIR/AnberVc.png"
fi

# 3. Zależności
python3 -c "import sdl2" 2>/dev/null || echo "UWAGA: brak pysdl2 — pip install pysdl2"
python3 -c "import PIL"  2>/dev/null || echo "UWAGA: brak Pillow — pip install Pillow"
python3 -c "import evdev" 2>/dev/null || echo "UWAGA: brak evdev — pip install evdev"

# 4. Self-test logiki (bez SDL)
echo "--- self-test ---"
python3 "$APP_DIR/vc_lib/core.py" || true

echo ""
echo "Zainstalowane. Uruchom 'AnberVc' z App Center."
