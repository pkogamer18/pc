#!/usr/bin/env bash
# Read-only GPU probe to run INSIDE DroidDeck's ARM64 Linux runtime.
set -u
echo "== Vulkan driver environment"
printf 'VK_DRIVER_FILES=%s\nVK_ICD_FILENAMES=%s\n' "${VK_DRIVER_FILES:-unset}" "${VK_ICD_FILENAMES:-unset}"
echo "== Available Vulkan ICDs"
find /usr/share/vulkan/icd.d -maxdepth 1 -type f -name '*.json' -print 2>/dev/null || true
echo "== Software driver libraries"
find /usr/lib -maxdepth 2 \( -name 'libvulkan_lvp.so' -o -name 'libvulkan_lvp.so.*' \) -print 2>/dev/null || true
echo "== Vulkan enumeration"
if command -v vulkaninfo >/dev/null 2>&1; then
  VK_LOADER_DEBUG=error vulkaninfo --summary 2>&1
else
  echo "MISSING: vulkaninfo (install vulkan-tools in Linux runtime)"
  exit 2
fi
