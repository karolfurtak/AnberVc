#!/bin/bash
# AnberVc launcher dla App Center / dmenu — dobór obrotów do średnicy narzędzia
export PYSDL2_DLL_PATH="/usr/lib"
export HOME=/root
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:/bin"
LOG=/mnt/data/anbervc.log
echo "$(date +%H:%M:%S): start" >> "$LOG"
cd /mnt/mmc/Roms/APPS/anbervc || exit 1
python3 app/main.py >> "$LOG" 2>&1
echo "$(date +%H:%M:%S): exit $?" >> "$LOG"
