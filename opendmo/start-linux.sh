#!/usr/bin/env sh
# OpenDMO launcher for Linux. Double-click (if your file manager allows) or run: ./start-linux.sh
cd "$(dirname "$0")" || exit 1
for c in python3.14 python3.13 python3.12 python3.11 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    exec "$c" run.py "$@"
  fi
done
echo ""
echo "[OpenDMO] Python 3.11 or newer was not found."
echo "  Debian/Ubuntu:  sudo apt install python3 python3-venv"
echo "  Fedora:         sudo dnf install python3"
echo "  Other:          https://www.python.org/downloads/"
echo "Then run ./start-linux.sh again."
exit 1
