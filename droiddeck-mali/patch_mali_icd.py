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
FRONTEND = "app/src/main/java/com/droiddeck/launcher/FrontEndActivity.kt"
GUEST_SESSION = "tools/linuxfs/overlay/usr/local/bin/droiddeck-session"
OLD_GUEST_HOOK = 'export GAMESCOPE_FORCE_VULKAN_REALTIME=${BL_GAMESCOPE_REALTIME:-0}'
NEW_GUEST_HOOK = '''# Experimental Mali path: prepare/validate the Linux ARM64 software Vulkan ICD.
if [ "${DROIDDECK_MALI_LVP:-0}" = 1 ]; then
  . /usr/local/bin/droiddeck-mali-lavapipe || exit 72
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
    pairs = [(RUNTIME, OLD_ICD, NEW_ICD), (SESSION, OLD_SESSION, NEW_SESSION), (FRONTEND, OLD_WARNING, NEW_WARNING), (GUEST_SESSION, OLD_GUEST_HOOK, NEW_GUEST_HOOK)]
    for name, old, new in pairs:
        src = (root / name).read_text()
        if new not in src and src.count(old) != 1:
            raise SystemExit(f"Unsupported upstream revision: {name}")
    for name, old, new in pairs:
        print(name, apply(root / name, old, new))

if __name__ == "__main__":
    main()
