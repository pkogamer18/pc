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
BOOTSTRAP_ANCHOR = '''        val root = LinuxRuntime.rootDir(this)
        val sessionRoot = LinuxRuntime.sessionRoot(this).apply { mkdirs() }'''
BOOTSTRAP_REPLACEMENT = '''        val root = LinuxRuntime.rootDir(this)
        // r9 is downloaded independently of the APK. Update its session script in-place
        // before proot launches; patching tools/linuxfs/overlay alone does not update r9.
        val maliGuest = Build.MODEL.equals("Z2464N", ignoreCase = true) ||
            Build.HARDWARE.contains("ums9632", ignoreCase = true) ||
            Build.SOC_MODEL.contains("ums9632", ignoreCase = true)
        if (maliGuest) {
            try {
                val script = File(root, "usr/local/bin/droiddeck-session")
                require(script.isFile) { "r9 session script missing: ${script.path}" }
                val staging = File(script.parentFile, ".droiddeck-session-mali-new")
                assets.open("mali/droiddeck-session").use { input ->
                    staging.outputStream().use { output -> input.copyTo(output) }
                }
                require(staging.setExecutable(true, false)) { "cannot mark Mali guest script executable" }
                if (!staging.renameTo(script)) {
                    staging.delete()
                    error("cannot replace r9 guest session script")
                }
                Log.i(TAG, "Mali guest: updated r9 session script from APK asset")
            } catch (e: Exception) {
                Log.e(TAG, "Mali guest: failed to update r9 session script", e)
                stopSession(72)
                return
            }
        }
        val sessionRoot = LinuxRuntime.sessionRoot(this).apply { mkdirs() }'''
MALI_INSTALL_ANCHOR = '''        val agentEnvironment = runCatching { com.droiddeck.launcher.agent.AgentEnv.beginSession(this) }'''
MALI_INSTALL_REPLACEMENT = '''        // UMS9632: provision Arch Linux ARM software Vulkan as fake root, never Android root.
        // This runs only if the ICD is missing, after the PRoot pack becomes available.
        if (maliGuest && AddonPack.PROOT.installed(this)) {
            val icdDir = File(root, "usr/share/vulkan/icd.d")
            val hasIcd = icdDir.listFiles()?.any {
                it.name.endsWith(".json") && (it.name.startsWith("lvp_icd") || it.name.contains("lavapipe"))
            } == true
            if (!hasIcd) {
                // Install the prebuilt Arch ARM64 bundle from the APK; no network or pacman.
                val archive = File(cacheDir, "mali-lavapipe-arm64.tar")
                try {
                    assets.open("mali/lavapipe-arm64.tar").use { input ->
                        archive.outputStream().use { output -> input.copyTo(output) }
                    }
                    val extraction = ProcessBuilder(
                        "/system/bin/toybox", "tar", "-xf", archive.absolutePath,
                        "-C", root.absolutePath
                    ).redirectErrorStream(true)
                        .redirectOutput(File(filesDir, "mali-lavapipe-extract.log"))
                        .start()
                    val extracted = extraction.waitFor(120, java.util.concurrent.TimeUnit.SECONDS)
                    if (!extracted) extraction.destroyForcibly()
                    val ready = extracted && extraction.exitValue() == 0 &&
                        icdDir.listFiles()?.any { it.name.startsWith("lvp_icd") && it.name.endsWith(".json") } == true
                    if (!ready) {
                        Log.e(TAG, "Mali: bundled Lavapipe extraction failed")
                        stopSession(72)
                        return
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Mali: bundled Lavapipe missing or invalid", e)
                    stopSession(72)
                    return
                } finally {
                    archive.delete()
                }
            }
            if (false) {
                val installLog = File(filesDir, "logs/mali-lavapipe-install.log")
                installLog.parentFile?.mkdirs()
                try {
                    val command = LinuxRuntime.prootPrefix(this, root, "/root", true).toMutableList()
                    command.addAll(listOf(
                        "-b", "/dev", "-b", "/proc", "-b", "/sys",
                        "/bin/sh", "-c",
                        "pacman -Sy --noconfirm --needed vulkan-swrast"
                    ))
                    val builder = ProcessBuilder(command)
                        .redirectErrorStream(true).redirectOutput(installLog)
                    builder.environment()["PROOT_LOADER"] = LinuxRuntime.prootLoader(this).absolutePath
                    builder.environment()["PROOT_TMP_DIR"] = LinuxRuntime.prootTempDir(this).absolutePath
                    val process = builder.start()
                    val completed = process.waitFor(180, java.util.concurrent.TimeUnit.SECONDS)
                    if (!completed) process.destroyForcibly()
                    val exitCode = if (completed) process.exitValue() else -1
                    val installed = icdDir.listFiles()?.any {
                        it.name.endsWith(".json") && (it.name.startsWith("lvp_icd") || it.name.contains("lavapipe"))
                    } == true
                    Log.i(TAG, "Mali Lavapipe provision completed=" + completed +
                        " exit=" + exitCode + " icd=" + installed)
                    if (exitCode != 0 || !installed) {
                        Log.e(TAG, "Mali Lavapipe unavailable; pacman output: " + installLog.absolutePath)
                        stopSession(72)
                        return
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Mali Lavapipe provision failed; inspect mali-lavapipe-install.log", e)
                }
            }
        }
        val agentEnvironment = runCatching { com.droiddeck.launcher.agent.AgentEnv.beginSession(this) }'''
FRONTEND = "app/src/main/java/com/droiddeck/launcher/FrontEndActivity.kt"
GUEST_SESSION = "tools/linuxfs/overlay/usr/local/bin/droiddeck-session"
OLD_GUEST_HOOK = 'export GAMESCOPE_FORCE_VULKAN_REALTIME=${BL_GAMESCOPE_REALTIME:-0}'
NEW_GUEST_HOOK = '''# Experimental Mali path: prepare/validate the Linux ARM64 software Vulkan ICD.
if [ "${DROIDDECK_MALI_LVP:-0}" = 1 ]; then
  # Inline bootstrap: the downloaded r9 rootfs does not contain APK-only helper files.
  echo "== droiddeck-mali: guest-patch=v2; mode=software-vulkan"
  bl_lvp_icd=
  for bl_candidate in /usr/share/vulkan/icd.d/lvp_icd.aarch64.json /usr/share/vulkan/icd.d/lvp_icd.arm64.json /usr/share/vulkan/icd.d/lvp_icd.json /usr/share/vulkan/icd.d/*lavapipe*.json /etc/vulkan/icd.d/lvp_icd*.json /etc/vulkan/icd.d/*lavapipe*.json; do
    if [ -r "$bl_candidate" ]; then bl_lvp_icd="$bl_candidate"; break; fi
  done
  if [ -z "$bl_lvp_icd" ]; then
    echo "== mali-lavapipe: no preinstalled guest ICD found"
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
  # Gamescope 3.16 aborts on this Mali software ICD during vkAllocateMemory.
  # Do not try it again for the Steam entry point: use the proven desktop
  # compositor instead, where Steam already opens on this handset.
  if [ "${1:-}" = steam ] && [ -z "${BL_INSIDE:-}" ]; then
    echo "== mali-lavapipe: bypassing crashing Gamescope; opening Linux desktop for Steam"
    mode=lxqt
  fi
  # Experimental lower-memory profile for Lavapipe, not hardware acceleration.
  export LP_NUM_THREADS=2 BL_MANGOAPP=0 BL_XWAYLAND_COUNT=1 BL_HDR=0
  if [ "${BL_WIDTH:-1280}" -gt 960 ] || [ "${BL_HEIGHT:-720}" -gt 540 ]; then
    export BL_WIDTH=960 BL_HEIGHT=540 BL_FOLLOW_OUTPUT=0 BL_GAMESCOPE_STRETCH_16X9=0
  fi
  echo "== mali-lavapipe: low-memory trial size=${BL_WIDTH:-960}x${BL_HEIGHT:-540} threads=$LP_NUM_THREADS mangoapp=off xwayland=1"
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
    pairs = [(RUNTIME, OLD_ICD, NEW_ICD), (SESSION, OLD_SESSION, NEW_SESSION), (SESSION, BOOTSTRAP_ANCHOR, BOOTSTRAP_REPLACEMENT), (SESSION, MALI_INSTALL_ANCHOR, MALI_INSTALL_REPLACEMENT), (FRONTEND, OLD_WARNING, NEW_WARNING), (GUEST_SESSION, OLD_GUEST_HOOK, NEW_GUEST_HOOK), (HOST_COMPOSITOR, OLD_HOST_COMPOSITOR, NEW_HOST_COMPOSITOR)]
    for name, old, new in pairs:
        src = (root / name).read_text()
        if new not in src and src.count(old) != 1:
            raise SystemExit(f"Unsupported upstream revision: {name}")
    for name, old, new in pairs:
        print(name, apply(root / name, old, new))

if __name__ == "__main__":
    main()
