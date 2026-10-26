# Z2464N Mali-G57 hardware-accelerated DroidDeck port

Status: research/engineering plan; **not a working gaming build**. No APK rebuild should be started on the strength of this document.

## Device and reproducible failures

- nubia Z2464N; Unisoc UMS9632; Android 15; Mali-G57 r49p1.
- Android Vulkan reports 1.3, but this does not establish Linux guest Vulkan compatibility.
- APK compiled and Android UI launches; Linux runtime r9 installed.
- Previous session: absent guest helper, fixed by inlining bootstrap.
- Latest session: `pacman` cannot install `vulkan-swrast` without root; no Lavapipe ICD; compositor not reached.
- Stock DroidDeck explicitly targets Adreno/Turnip. This port must never pretend Turnip supports Mali.

## Architecture: three different graphics problems

1. **Android host display compositor**: `CompositorHost` -> `WaylandCompositor.nativeStartWithSurface` and driver selection. On Mali, use Android's vendor Vulkan loader/ICD via the system Vulkan loader where permitted; do not load AdrenoTools Turnip.
2. **Linux ARM64 guest compositor (gamescope)**: proot/glibc process, cannot dlopen Android Bionic Mali driver directly. Need an explicitly implemented host Vulkan RPC bridge (with external memory/synchronization support) OR a proven native guest driver. Validate VkInstance, physical device enumeration, swapchain/presentation separately.
3. **x86/x64 game path**: FEX Vulkan thunk, DXVK/Proton; requires extensions and memory features unavailable or unverified on device. Must validate independently of the Steam client.

## Why the previous Lavapipe approach is insufficient

- APK asset staging is not the same as installing assets into separately downloaded Linux r9.
- `pacman -Sy` from unprivileged proot fails; avoid mutating the distro package database at session start.
- Lavapipe/llvmpipe are CPU renderers; they are suitable for proving the guest compositor startup, **not** for promising playable Windows games.
- Guest ICD JSON must refer to a glibc ARM64 shared library with all dependent libraries present; architecture, loader ABI and `vulkaninfo --summary` must be verified before Gamescope.
- Do not ship a fake ICD JSON or redirect a glibc loader to Bionic system libraries.

## Workstreams and gates (no expensive APK build until all offline gates pass)

### Gate A: device Vulkan capability capture

Collect Android `vulkaninfo` (or a native Android Vulkan probe) including physical-device name, Vulkan API, required extensions, external memory/semaphore support, queue families, format support, and BC texture support. Record GPU driver version. Avoid requiring root.

### Gate B: host presentation on Mali

Trace Android native Wayland compositor initialization and its driver-selection paths. Add an explicit Mali mode using Android's system Vulkan loader, disable Turnip/AdrenoTools paths and KGSL-specific assumptions, and write host-side tests. Test rendering a triangle to the app surface without Linux.

### Gate C: Linux guest Vulkan bridge feasibility

Inventory existing Vulkan host/guest transport and FEX thunk; if no bridge exists, design protocol for instance/device/resource handles, external memory and synchronization. Build a tiny guest Vulkan enumerate/clear/present test before attempting Gamescope. Do not assume PanVK can access the Android Mali kernel interface: check GPU generation, /dev nodes, driver binding and sandbox access first.

### Gate D: CPU fallback diagnostic

As an independent smoke test, package a verified ARM64 glibc Lavapipe build plus its runtime dependencies as an optional add-on, extract under app-private Linux filesystem without root/pacman, validate ICD path and dependencies, and run `vulkaninfo`. This does not substitute for Gate C.

### Gate E: Steam and games

Only after host and guest Vulkan pass: gamescope startup -> Steam UI -> FEX x86 Vulkan test -> DXVK sample -> one lightweight game. Measure FPS, frame pacing, temperature, memory, battery, and stability. Avoid performance promises.

## Next source changes

- Identify and separate `LinuxVulkanDriver` selection from Android display driver selection; avoid using an Adreno default on Mali.
- Inspect `WaylandCompositor` native Vulkan initialization and the actual `libvulkan.so` loading path.
- Remove automatic `pacman` attempts from Mali session startup once a verified fallback add-on exists.
- Add a standalone CI job for static analysis and native Vulkan smoke tests; leave full APK job manual until gate results warrant it.

## Hard limits

The user's requested goal is hardware-accelerated playable Steam, **not merely an APK that builds**. The present repository does not implement a Vulkan RPC bridge or a working Mali guest driver. No one can responsibly certify performance or compatibility without device measurements.
