#!/usr/bin/env bash
# Produce a reproducible patched-source artifact. NOT an Android APK.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="${1:-$PWD/build/mali-experiment}"
mkdir -p "$work"
if [[ ! -d "$work/upstream/.git" ]]; then
  git clone --depth 1 https://github.com/Droid-Deck/DroidDeck.git "$work/upstream"
fi
python3 "$here/patch_mali_icd.py" "$work/upstream"
git -C "$work/upstream" diff --check
git -C "$work/upstream" diff --binary > "$work/mali-g57.patch"
git -C "$work/upstream" rev-parse HEAD > "$work/upstream-sha.txt"
cp "$here/STATUS.md" "$work/STATUS.md"
echo "Patched source and patch ready at $work"
echo "No APK was built. A glibc ARM64 Lavapipe runtime and device tests are still required."
