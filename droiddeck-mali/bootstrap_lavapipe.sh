#!/usr/bin/env bash
# Run only in the ARM64 Linux guest on the explicit Mali experiment path.
set -u
log() { echo "== mali-lavapipe: $*"; }
[ "${DROIDDECK_MALI_LVP:-0}" = 1 ] || exit 0
case "$(uname -m)" in aarch64|arm64) ;; *) log "not an ARM64 guest"; exit 0 ;; esac
find_icd() {
  local f
  for f in /usr/share/vulkan/icd.d/lvp_icd.aarch64.json /usr/share/vulkan/icd.d/lvp_icd.arm64.json /usr/share/vulkan/icd.d/lvp_icd.json /usr/share/vulkan/icd.d/*lavapipe*.json; do
    [ -f "$f" ] && { printf '%s\n' "$f"; return 0; }
  done
  return 1
}
icd=$(find_icd || :)
if [ -z "$icd" ]; then
  log "Lavapipe ICD absent; trying Arch Linux ARM vulkan-swrast package"
  if [ "$(id -u)" = 0 ] && command -v pacman >/dev/null 2>&1; then
    if command -v timeout >/dev/null 2>&1; then
      timeout 240 pacman -Sy --needed --noconfirm vulkan-swrast || log "pacman install failed; check DNS/mirrors and package names"
    else
      pacman -Sy --needed --noconfirm vulkan-swrast || log "pacman install failed"
    fi
  else
    log "cannot install: root/pacman unavailable; a packaged glibc ARM64 Lavapipe ICD is required"
  fi
  icd=$(find_icd || :)
fi
if [ -z "$icd" ]; then
  log "FATAL: no Lavapipe ICD; cannot start a Vulkan compositor on the software path"
  exit 72
fi
lib=$(sed -n 's/.*"library_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$icd" | head -1)
if [ -z "$lib" ]; then log "FATAL: ICD has no library_path: $icd"; exit 72; fi
case "$lib" in /*) ;; *) lib="$(dirname "$icd")/$lib" ;; esac
if [ ! -r "$lib" ]; then
  log "FATAL: ICD library missing: $lib"
  exit 72
fi
export VK_DRIVER_FILES="$icd"
export VK_ICD_FILENAMES="$icd"
export GALLIUM_DRIVER=llvmpipe
export LIBGL_ALWAYS_SOFTWARE=1
log "selected $icd -> $lib"
if command -v vulkaninfo >/dev/null 2>&1; then
  vulkaninfo --summary 2>&1 | head -45 || log "vulkaninfo failed"
fi
