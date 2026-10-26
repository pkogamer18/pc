#!/usr/bin/env python3
"""Patch upstream DroidDeck's Linux Vulkan ICD and Steam-session GPU settings."""
from pathlib import Path
import argparse

RUNTIME = "app/src/main/java/com/droiddeck/launcher/runtime/LinuxRuntime.java"
SESSION = "app/src/main/java/com/droiddeck/launcher/session/SessionService.kt"
OLD_ICD = '''        for (File manifest : manifests) {
            if (manifest.getName().contains("freedreno")) return manifest;
        }
        return manifests.length > 0 ? manifests[0] : null;'''
NEW_ICD = '''        // UMS9632 experiment: never select Qualcomm Freedreno for a Mali GPU.
        if ((android.os.Build.MODEL.equalsIgnoreCase("Z2464N") || android.os.Build.HARDWARE.toLowerCase(java.util.Locale.ROOT).contains("ums9632") || android.os.Build.SOC_MODEL.toLowerCase(java.util.Locale.ROOT).contains("ums9632"))) {
            for (File manifest : manifests) {
                String name = manifest.getName().toLowerCase(java.util.Locale.ROOT);
                if (name.startsWith("lvp_icd") || name.contains("lavapipe")) return manifest;
            }
            android.util.Log.e("LinuxRuntime", "UMS9632: no Lavapipe ICD in Linux rootfs");
            return null;
        }
        for (File manifest : manifests) {
            if (manifest.getName().contains("freedreno")) return manifest;
        }
        return manifests.length > 0 ? manifests[0] : null;'''
HOST_COMPOSITOR = "app/src/main/java/com/droiddeck/launcher/wayland/CompositorHost.kt"
OLD_HOST_COMPOSITOR = '''        com.droiddeck.launcher.gpu.TpUbwcHint.applyToProcess(context)
        WaylandCompositor.nativeStartWithSurface(
            surface, xdgRuntimeDir, driverPath, libraryName, nativeLibDir,
        )'''
NEW_HOST_COMPOSITOR = '''        // Z2464N has a working Android vendor Vulkan ICD, not a Turnip/Adreno ICD.
        // Passing null selects the Android system Vulkan loader in vk_loader_open.
        // This affects host presentation only; guest Linux Vulkan is separate.
        val maliHost = android.os.Build.MODEL.equals("Z2464N", ignoreCase = true) ||
            android.os.Build.HARDWARE.contains("ums9632", ignoreCase = true) ||
            android.os.Build.SOC_MODEL.contains("ums9632", ignoreCase = true)
        if (maliHost) {
            android.util.Log.i("CompositorHost", "Mali host: Android system Vulkan loader, no Turnip/UBWC")
        } else {
            com.droiddeck.launcher.gpu.TpUbwcHint.applyToProcess(context)
        }
        WaylandCompositor.nativeStartWithSurface(
            surface, xdgRuntimeDir,
            if (maliHost) null else driverPath,
            if (maliHost) null else libraryName,
            nativeLibDir,
        )'''
FRONTEND = "app/src/main/java/com/droiddeck/launcher/FrontEndActivity.kt"
GUEST_SESSION = "tools/linuxfs/overlay/usr/local/bin/droiddeck-session"
OLD_GUEST_HOOK = 'export GAMESCOPE_FORCE_VULKAN_REALTIME=${BL_GAMESCOPE_REALTIME:-0}'
NEW_GUEST_HOOK = '''# Experimental Mali path: prepare/validate the Linux ARM64 software Vulkan ICD.
if [ "${DROIDDECK_MALI_LVP:-0}" = 1 ]; then
  # Inline bootstrap: the downloaded r9 rootfs does not contain APK-only helper files.
  bl_lvp_icd=
  for bl_candidate in /usr/share/vulkan/icd.d/lvp_icd.aarch64.json /usr/share/vulkan/icd.d/lvp_icd.arm64.json /usr/share/vulkan/icd.d/lvp_icd.json /usr/share/vulkan/icd.d/*lavapipe*.json; do
    if [ -r "$bl_candidate" ]; then bl_lvp_icd="$bl_candidate"; break; fi
  done
  if [ -z "$bl_lvp_icd" ]; then
    echo "== mali-lavapipe: ICD absent; trying vulkan-swrast via pacman"
    echo "== mali-lavapipe: rootless runtime; ICD must be installed offline, not with pacman"
    for bl_candidate in /usr/share/vulkan/icd.d/lvp_icd.aarch64.json /usr/share/vulkan/icd.d/lvp_icd.arm64.json /usr/share/vulkan/icd.d/lvp_icd.json /usr/share/vulkan/icd.d/*lavapipe*.json; do
      if [ -r "$bl_candidate" ]; then bl_lvp_icd="$bl_candidate"; break; fi
    done
  fi
  if [ -z "$bl_lvp_icd" ]; then
    echo "== mali-lavapipe: FATAL no ARM64 Lavapipe ICD installed"
    exit 72
  fi
  bl_lvp_lib=$(sed -n 's/.*"library_path"[[:space:]]*:[[:space:]]*"\\([^"]*\\)".*/\\1/p' "$bl_lvp_icd" | head -1)
  if [ -z "$bl_lvp_lib" ]; then
    echo "== mali-lavapipe: FATAL ICD has no library_path"
    exit 72
  fi
  case "$bl_lvp_lib" in
    /*) bl_lvp_resolved="$bl_lvp_lib" ;;
    */*) bl_lvp_resolved="$(dirname "$bl_lvp_icd")/$bl_lvp_lib" ;;
    *)
      bl_lvp_resolved=
      for bl_dir in /usr/lib /usr/lib/aarch64-linux-gnu /lib /lib/aarch64-linux-gnu; do
        if [ -r "$bl_dir/$bl_lvp_lib" ]; then bl_lvp_resolved="$bl_dir/$bl_lvp_lib"; break; fi
      done
      ;;
  esac
  if [ -z "$bl_lvp_resolved" ] || [ ! -r "$bl_lvp_resolved" ]; then
    echo "== mali-lavapipe: FATAL missing library $bl_lvp_lib"
    exit 72
  fi
  export VK_ICD_FILENAMES="$bl_lvp_icd" VK_DRIVER_FILES="$bl_lvp_icd"
  export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
  echo "== mali-lavapipe: selected $bl_lvp_icd ($bl_lvp_resolved)"
  unset bl_lvp_icd bl_lvp_lib bl_lvp_resolved bl_dir bl_candidate
fi
export GAMESCOPE_FORCE_VULKAN_REALTIME=${BL_GAMESCOPE_REALTIME:-0}'''
OLD_WARNING = '''                        title = androidx.compose.ui.res.stringResource(R.string.main_non_adreno_title),
                        text = androidx.compose.ui.res.stringResource(R.string.main_non_adreno_text, com.droiddeck.launcher.core.DeviceSupport.gpuName(this@FrontEndActivity), release.size / 1e6),'''
NEW_WARNING = '''                        title = if (android.os.Build.MODEL.equals("Z2464N", ignoreCase = true))
                            "Mali-G57: Vulkan experimental"
                        else androidx.compose.ui.res.stringResource(R.string.main_non_adreno_title),
                        text = if (android.os.Build.MODEL.equals("Z2464N", ignoreCase = true))
                            "Este dispositivo usa Mali-G57, no Adreno. Turnip no es compatible. La selección experimental de Lavapipe requiere un ICD Linux ARM64 real, que todavía no está incluido en esta compilación. Instalar el runtime (%.0f MB) no garantiza que Steam o Gamescope funcionen.".format(java.util.Locale.ROOT, release.size / 1e6)
                        else androidx.compose.ui.res.stringResource(R.string.main_non_adreno_text, com.droiddeck.launcher.core.DeviceSupport.gpuName(this@FrontEndActivity), release.size / 1e6),'''

OLD_SESSION = '''        guest.add("MESA_LOADER_DRIVER_OVERRIDE=zink")
        guest.add("GALLIUM_DRIVER=zink")
        guest.add("LIBGL_KOPPER_DRI2=true")
        LinuxRuntime.vulkanIcd(this)?.let { guest.add("VK_ICD_FILENAMES=" + it.path) }'''
NEW_SESSION = '''        val maliSoftwareMode = android.os.Build.MODEL.equals("Z2464N", ignoreCase = true) ||
            android.os.Build.HARDWARE.contains("ums9632", ignoreCase = true) ||
            android.os.Build.SOC_MODEL.contains("ums9632", ignoreCase = true)
        if (maliSoftwareMode) {
            guest.add("DROIDDECK_MALI_LVP=1")\n            guest.add("LIBGL_ALWAYS_SOFTWARE=1")
            guest.add("GALLIUM_DRIVER=llvmpipe")
            val softwareIcd = LinuxRuntime.vulkanIcd(this)
            if (softwareIcd != null) {
                guest.add("VK_ICD_FILENAMES=" + softwareIcd.path)
                guest.add("VK_DRIVER_FILES=" + softwareIcd.path)
            } else {
                android.util.Log.e("SessionService", "UMS9632: no Lavapipe ICD; Gamescope may not start")
            }
        } else {
            guest.add("MESA_LOADER_DRIVER_OVERRIDE=zink")
            guest.add("GALLIUM_DRIVER=zink")
            guest.add("LIBGL_KOPPER_DRI2=true")
            LinuxRuntime.vulkanIcd(this)?.let { guest.add("VK_ICD_FILENAMES=" + it.path) }
        }'''

def apply(path, old, new):
    source = path.read_text()
    if new in source: return "already patched"
    if source.count(old) != 1: raise RuntimeError(f"Unsupported upstream revision: {path}")
    path.write_text(source.replace(old, new))
    return "patched"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("upstream", type=Path)
    root = ap.parse_args().upstream
    pairs = [(RUNTIME, OLD_ICD, NEW_ICD), (SESSION, OLD_SESSION, NEW_SESSION), (FRONTEND, OLD_WARNING, NEW_WARNING), (GUEST_SESSION, OLD_GUEST_HOOK, NEW_GUEST_HOOK), (HOST_COMPOSITOR, OLD_HOST_COMPOSITOR, NEW_HOST_COMPOSITOR)]
    for name, old, new in pairs:
        src = (root / name).read_text()
        if new not in src and src.count(old) != 1:
            raise SystemExit(f"Unsupported upstream revision: {name}")
    for name, old, new in pairs:
        print(name, apply(root / name, old, new))

if __name__ == "__main__":
    main()
