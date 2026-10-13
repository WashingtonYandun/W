#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$HOME/.local/bin}"

echo "=================================================="
echo "W Language v0.1 — Toolchain Installer"
echo "=================================================="

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 is required (>= 3.10)." >&2
    exit 1
fi

if ! command -v cc >/dev/null 2>&1; then
    echo "[ERROR] A C99 compiler (cc / clang / gcc) is required." >&2
    exit 1
fi

chmod +x "$REPO_ROOT/w"

echo "[1/2] Pre-building Stage-2 native self-hosted W1 compiler..."
mkdir -p "$REPO_ROOT/.w_cache"
"$REPO_ROOT/w" build --selfhost "$REPO_ROOT/selfhost/w1.w" -o "$REPO_ROOT/.w_cache/w1"

echo "[2/2] Installing 'w' CLI into $TARGET_DIR..."
mkdir -p "$TARGET_DIR"
ln -sf "$REPO_ROOT/w" "$TARGET_DIR/w"

echo "=================================================="
echo "[OK] Installed: $TARGET_DIR/w -> $REPO_ROOT/w"
"$TARGET_DIR/w" version
echo "=================================================="

case ":$PATH:" in
    *":$TARGET_DIR:"*)
        echo "You can now run 'w' from any directory."
        ;;
    *)
        echo "NOTE: Add $TARGET_DIR to your PATH if not already present:"
        echo "  export PATH=\"$TARGET_DIR:\$PATH\""
        ;;
esac
