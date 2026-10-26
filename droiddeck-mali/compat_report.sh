#!/usr/bin/env bash
# DroidDeck Mali-G57 compatibility report. Read-only; no root or package installation.
set -u
printf 'DroidDeck Mali-G57 compatibility report\n'
printf 'kernel: '; uname -a
printf 'architecture: '; uname -m
printf 'display: %s wayland: %s\n' "${DISPLAY:-unset}" "${WAYLAND_DISPLAY:-unset}"
for p in /dev/mali /dev/mali0 /dev/mali_kbase /dev/dri/renderD128 /dev/dri/card0; do
  if [ -e "$p" ]; then
    printf '%s: present, ' "$p"
    [ -r "$p" ] && printf 'readable ' || printf 'not-readable '
    [ -w "$p" ] && printf 'writable\n' || printf 'not-writable\n'
  else printf '%s: absent\n' "$p"; fi
done
printf 'Vulkan ICDs:\n'
for d in /usr/share/vulkan/icd.d /etc/vulkan/icd.d; do
  [ ! -d "$d" ] || find "$d" -maxdepth 1 -name '*.json' -print
done
printf 'OpenGL software flags: LIBGL_ALWAYS_SOFTWARE=%s GALLIUM_DRIVER=%s\n' "${LIBGL_ALWAYS_SOFTWARE:-unset}" "${GALLIUM_DRIVER:-unset}"
for cmd in FEX vulkaninfo glxinfo droiddeck-fex droiddeck-proton-run; do
  if command -v "$cmd" >/dev/null 2>&1; then printf '%s: %s\n' "$cmd" "$(command -v "$cmd")"; else printf '%s: unavailable\n' "$cmd"; fi
done
printf 'Steam installation:\n'
for d in "$HOME/.local/share/Steam" "$HOME/.steam/steam"; do
  [ ! -d "$d" ] || printf '%s exists\n' "$d"
done
printf 'Half-Life manifest:\n'
for f in "$HOME/.local/share/Steam/steamapps/appmanifest_70.acf" /mnt/droiddeck/steamapps/appmanifest_70.acf; do
  [ ! -f "$f" ] || printf '%s exists\n' "$f"
done
printf 'NOTE: Android Vulkan vendor drivers cannot be loaded directly by Linux glibc.\n'
printf 'NOTE: This report does not change GPU settings, Steam, or the kernel.\n'
