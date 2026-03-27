#!/bin/bash
# Double-click this file on macOS to launch EMIT Converter
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/venv/bin/activate"
python3 "$DIR/emit_gui.py"
