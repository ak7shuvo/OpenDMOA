#!/usr/bin/env bash
# OpenDMO launcher for macOS. Double-click in Finder (first time: right-click > Open).
cd "$(dirname "$0")" || exit 1
for c in python3.14 python3.13 python3.12 python3.11 python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    "$c" run.py "$@"
    status=$?
    [ $status -ne 0 ] && read -r -p "Press Enter to close…" _
    exit $status
  fi
done
echo ""
echo "[OpenDMO] Python 3.11 or newer was not found."
echo "  Install it from https://www.python.org/downloads/macos/  (or: brew install python@3.12)"
echo "  Then double-click start-mac.command again."
read -r -p "Press Enter to close…" _
exit 1
