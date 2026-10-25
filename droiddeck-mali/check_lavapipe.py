#!/usr/bin/env python3
"""Verify a Linux ARM64 Lavapipe ICD and its library are present in a rootfs."""
import argparse
import json
from pathlib import Path
import struct

def inspect(root):
    icd_dir = root / "usr/share/vulkan/icd.d"
    manifests = sorted(icd_dir.glob("lvp_icd*.json")) + sorted(icd_dir.glob("*lavapipe*.json"))
    if not manifests:
        raise RuntimeError("Lavapipe manifest absent; runtime must be rebuilt")
    for manifest in manifests:
        data = json.loads(manifest.read_text())
        name = data.get("ICD", {}).get("library_path")
        if not name:
            continue
        library = Path(name)
        library = root / library.relative_to("/") if library.is_absolute() else manifest.parent / library
        if not library.is_file():
            continue
        header = library.read_bytes()[:20]
        if len(header) < 20 or header[:4] != b"\x7fELF":
            continue
        order = "<" if header[5] == 1 else ">"
        machine = struct.unpack(order + "H", header[18:20])[0]
        if header[4] == 2 and machine == 183:
            return manifest, library
    raise RuntimeError("No manifest references an ARM64 ELF Lavapipe library")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("rootfs", type=Path)
    a = p.parse_args()
    try:
        manifest, library = inspect(a.rootfs.resolve())
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as e:
        p.exit(1, f"NOT READY: {e}\n")
    print(f"ARM64 Lavapipe packaging found: {manifest} -> {library}")
    print("Still requires on-device Vulkan enumeration and Gamescope tests.")
