# DroidDeck Mali-G57 compatibility lab

Target: nubia Z2464N, Android 15 (API 35), Unisoc UMS9632, ARM64, Mali-G57 r49p1, Vulkan 1.3.278.

Upstream: https://github.com/Droid-Deck/DroidDeck (GPL-3.0).

## Status

**Research/diagnostics only. No working modified APK yet.** The upstream application explicitly does not support Mali. This folder is a separate compatibility experiment, not a claim that removing a warning enables graphics.

The phone's Vulkan 1.3 driver is an Android ARM64 driver. The Linux runtime, FEX x86-64 Vulkan thunk, and compositor have separate loader/ABI requirements. Android Vulkan availability does not prove Vulkan works inside the Linux runtime.

## Initial findings

- `app/src/main/java/com/droiddeck/launcher/gpu/TurnipDriver.java`: bundled driver IDs and AdrenoTools ZIP loading. Its help text requires AdrenoTools `vulkan.adXXXX.so` packages.
- `tools/linuxfs/fex/vulkanpin.c`: intercepts Vulkan entry points and filters display-related extensions; changing a GPU name is not enough.
- Upstream README says Mali unsupported and desktop compositing uses software rendering.
- The device's Vulkan report says BC textures and VK_EXT_robustness2 are unavailable; DXVK/game compatibility must be checked separately.

## Steps before a real patch

1. Export the **Share logs** ZIP after one Steam launch failure and run `python3 analyze_session.py path/to/session.log`. Redact any tokens before uploading.
2. Trace the compositor Vulkan instance/device creation and whether it can use Android's native Mali ICD without the AdrenoTools override.
3. Trace the ARM64 Linux Vulkan loader and FEX thunk/ICD requirements; do not inject Android Bionic drivers into glibc as though they were interchangeable.
4. Build a separate experimental APK with a different application ID/signature and no overwrite of the existing install.
5. Test compositor initialization, Steam UI, then DXVK/Proton independently.

## Building upstream

See upstream `tools/build_local.sh`: requires Docker, Java 17, Android SDK/NDK, Rust, Python 3, zstd and GitHub CLI. The upstream build cannot be represented as a simple Gradle-only build without its prepared native artifacts.

## Safety

Do not flash system GPU libraries, replace vendor partitions, or install random driver ZIPs. Keep the official APK and runtime backups until the experimental build is validated.
