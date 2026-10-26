#!/bin/sh
# Read-only Mali GPU access probe for DroidDeck Linux/PRoot (no root required).
# Never assumes that the Android vendor Vulkan ICD is loadable inside glibc Linux.
set -u
echo "== Mali-G57 GPU access probe =="
echo "arch=$(uname -m)"
for p in /dev/mali /dev/mali0 /dev/mali_kbase /dev/dri/renderD128 /dev/dri/card0 /dev/kgsl-3d0; do
  if [ -e "$p" ]; then
    if [ -r "$p" ] && [ -w "$p" ]; then state=rw
    elif [ -r "$p" ]; then state=read-only
    else state=permission-denied
    fi
    echo "device $p: $state"
  else
    echo "device $p: absent"
  fi
done
for p in /sys/class/misc/mali0/device /sys/class/drm/renderD128/device; do
  if [ -e "$p" ]; then echo "sysfs $p: present"; fi
done
for cmd in vulkaninfo glxinfo eglinfo; do
  if command -v "$cmd" >/dev/null 2>&1; then echo "tool $cmd: present"; else echo "tool $cmd: missing"; fi
done
echo "note: /dev access alone does not prove Panfrost/PanVK compatibility"
echo "note: Android's vendor Vulkan library cannot be directly used as a Linux glibc ICD"
