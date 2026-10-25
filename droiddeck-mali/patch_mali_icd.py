#!/usr/bin/env python3
"""Apply a conservative Mali Vulkan ICD selection patch to an upstream DroidDeck checkout."""
from pathlib import Path
import sys

TARGET = Path("app/src/main/java/com/droiddeck/launcher/runtime/LinuxRuntime.java")
OLD = '''        for (File manifest : manifests) {
            if (manifest.getName().contains("freedreno")) return manifest;
        }
        return manifests.length > 0 ? manifests[0] : null;'''
NEW = '''        // Experimental Mali path: never force Qualcomm Freedreno on a Mali GPU.
        // A Linux ARM64 lavapipe ICD must be included in the rootfs for this to work.
        // Android's Bionic Mali driver is not a drop-in glibc Linux ICD.
        String gpu = android.opengl.GLES20.glGetString(android.opengl.GLES20.GL_RENDERER);
        // GL context may not exist on this thread: use Vulkan vendor ID via
        // Android system properties only as a conservative supplementary hint.
        String hardware = android.os.Build.HARDWARE.toLowerCase(java.util.Locale.ROOT);
        boolean targetUnisoc = hardware.contains("ums9632");
        if (targetUnisoc) {
            for (File manifest : manifests) {
                String name = manifest.getName().toLowerCase(java.util.Locale.ROOT);
                if (name.contains("lvp") || name.contains("lavapipe")) return manifest;
            }
            android.util.Log.w("LinuxRuntime", "UMS9632: no Lavapipe ICD in Linux rootfs; refusing Freedreno");
            return null;
        }
        for (File manifest : manifests) {
            if (manifest.getName().contains("freedreno")) return manifest;
        }
        return manifests.length > 0 ? manifests[0] : null;'''
def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    path = root / TARGET
    original = path.read_text()
    if NEW in original:
        print("Already patched")
        return
    if original.count(OLD) != 1:
        raise SystemExit("Upstream code changed: patch not applied")
    path.write_text(original.replace(OLD, NEW))
    print(f"Patched {path}; note: no Lavapipe binary is bundled by this patch")
if __name__ == "__main__":
    main()
