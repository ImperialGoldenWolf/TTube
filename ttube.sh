#!/bin/bash
# TTube - Terminal YouTube Audio Streamer
# Linux/macOS Launcher

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo ""
    echo "[!] Virtual environment not found!"
    echo "[>] Please run: python3 install_app.py"
    echo ""
    exit 1
fi

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Set terminal options for better rendering
export TERM=xterm-256color

echo ""
echo "[*] Starting TTube Terminal Audio Streamer..."
echo ""

# Run TTube
python -m ttube

echo ""
echo "[*] TTube closed."
echo ""
