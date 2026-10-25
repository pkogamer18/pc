# Session findings

The submitted DroidDeck diagnostic archive shows Gamescope failing to enumerate a Vulkan physical device. The runtime selected a Freedreno Vulkan ICD despite the device using a Mali-G57 GPU. A subsequent SDL error reports that the Wayland surface extension was not enabled, and Gamescope could not create its backend.

The guest process exited with status 0 and the Android crash buffer was empty. These logs do not show a Steam or FEX crash.

Next steps: trace ICD selection, investigate a Mali-compatible Linux Vulkan backend or software Lavapipe, verify Vulkan enumeration, then retry Gamescope before Steam. Do not assume Android's Vulkan driver can be loaded directly by a glibc Linux runtime.
