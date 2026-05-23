#!/usr/bin/env bash
# run.sh — universal entry point for Replit dev shell and autoscale deployment.
# Finds Python without hardcoding nix store paths, sets PYTHONPATH, starts bot.

set -e

# Source Replit nix environment if available (dev shell only — no-op in containers)
if [ -f /etc/profile.d/replit.sh ]; then
  source /etc/profile.d/replit.sh
fi

# Find the best available Python 3 binary
PYTHON=""
for candidate in python3.11 python3.10 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERROR: No Python interpreter found in PATH." >&2
  exit 1
fi

echo "Starting bot with $PYTHON ($($PYTHON --version 2>&1))"

# Add .pythonlibs to PYTHONPATH so Replit-installed packages are found
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}.pythonlibs/lib/python/site-packages"

exec "$PYTHON" main.py
