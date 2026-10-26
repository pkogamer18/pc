# Mali-G57 experiment status

Target: nubia Z2464N, UMS9632, Mali-G57, Android 15.

## Implemented
- A strict upstream source patch for LinuxRuntime.java and SessionService.kt.
- On UMS9632, prefer a packaged Lavapipe ICD rather than Freedreno; select llvmpipe for OpenGL and avoid forcing Zink.
- ARM64 Lavapipe packaging validator and Python unit tests.
- GitHub Actions job to check source patch application and unit tests.

## Not yet done
- **No Lavapipe binary or dependencies have been built and installed in DroidDeck's Linux rootfs.**
- No full DroidDeck APK build or installation.
- No proof that Gamescope can create a Vulkan device and Wayland surface.
- No Steam/Proton or game compatibility validation.

## Next gate
Build ARM64 Mesa Lavapipe and dependencies for the Linux/glibc runtime; include an ICD manifest that references the actual library, then run the packaging validator. Next test vulkaninfo inside the compositor session and the Wayland surface extension. A native Android Mali driver cannot simply be copied into a glibc runtime.

This experiment is not a functional APK and should not be advertised as such.
