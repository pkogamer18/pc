#!/usr/bin/env python3
"""Offline regression checks for Mali patch, without building an APK."""
from pathlib import Path
import ast
import subprocess
import tempfile
import sys

root = Path(__file__).resolve().parent
patch = root / "patch_mali_icd.py"
ast.parse(patch.read_text())
sys.path.insert(0, str(root))
import patch_mali_icd as p

assert "pacman -Sy" not in p.NEW_GUEST_HOOK, "Never run pacman as ordinary guest user"
assert "prootPrefix" not in p.BOOTSTRAP_REPLACEMENT, "Do not reintroduce untested fake-root bootstrap"
assert "assets.open(\"mali/droiddeck-session\")" in p.BOOTSTRAP_REPLACEMENT
assert "guest-patch=v2" in p.NEW_GUEST_HOOK
assert 'if [ "$mode" = steam ]' in p.NEW_GUEST_HOOK, "Steam fallback must inspect mode, not shifted positional arguments"
assert "mode=lxqt" in p.NEW_GUEST_HOOK, "Mali must bypass the Gamescope entry point"
assert 'if [ "${1:-}" = steam ]' not in p.NEW_GUEST_HOOK
assert "DROIDDECK_MALI_LVP" in p.NEW_SESSION
assert "VK_ICD_FILENAMES" in p.NEW_SESSION
assert "Turnip no es compatible" in p.NEW_WARNING
assert "lvp_icd" in p.NEW_ICD
assert "exit 72" in p.NEW_GUEST_HOOK
assert "if (maliHost) null else driverPath" in p.NEW_HOST_COMPOSITOR
assert "if (maliHost) null else libraryName" in p.NEW_HOST_COMPOSITOR
assert "TpUbwcHint.applyToProcess(context)" in p.NEW_HOST_COMPOSITOR

with tempfile.TemporaryDirectory() as d:
    shell = Path(d) / "session.sh"
    shell.write_text("#!/bin/sh\n" + p.NEW_GUEST_HOOK + "\n")
    subprocess.run(["sh", "-n", str(shell)], check=True)
print("PASS: Mali source, guest shell syntax, and rootless Vulkan guards")
