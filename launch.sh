#!/usr/bin/env bash
# F1 Telemetry Launcher (Linux / macOS)
# Double-click or run: ./launch.sh

set -e

echo ""
echo "========================================================"
echo "        F1 TELEMETRY  —  Multi-Game Dashboard"
echo "        Supports F1 2019 · F1 2020 · F1 2021"
echo "========================================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find Python 3
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "[ERROR] Python 3 is not installed."
    echo "Install it via your package manager, e.g.:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv"
    echo "  macOS:         brew install python3"
    exit 1
fi

exec "$PY" "$SCRIPT_DIR/launch.py"
