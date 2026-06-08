#!/usr/bin/env bash
#
# One-paste local setup. Clones (or updates) the repo, then runs setup.sh,
# which installs deps, asks for your Canvas URL + token once, opens a public
# tunnel, and registers it with Poke.
#
#   curl -fsSL https://raw.githubusercontent.com/jackulau/PokeCanvas/main/bootstrap.sh | bash
#
# Or with a custom target directory:
#   curl -fsSL .../bootstrap.sh | bash -s -- my-canvas-dir

set -euo pipefail

REPO_URL="${POKE_CANVAS_REPO:-https://github.com/jackulau/PokeCanvas}"
TARGET_DIR="${1:-PokeCanvas}"

command -v git >/dev/null 2>&1 || { echo "git is required: https://git-scm.com/downloads" >&2; exit 1; }

if [ -d "$TARGET_DIR/.git" ]; then
  echo "==> Updating existing checkout in $TARGET_DIR"
  git -C "$TARGET_DIR" pull --ff-only
else
  echo "==> Cloning $REPO_URL into $TARGET_DIR"
  git clone --depth 1 "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
chmod +x setup.sh 2>/dev/null || true
echo "==> Launching setup.sh"
exec ./setup.sh
