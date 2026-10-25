#!/usr/bin/env python3
"""Read-only DroidDeck session log triage. Never uploads data."""
import argparse
import pathlib
import re

PATTERNS = {
    "vulkan": r"VK_ERROR_|vkCreate|vulkan|ICD|libvulkan|turnip|adreno|mali",
    "runtime": r"FEX|proot|exec format|ld\.so|shared librar|not found|dlopen",
    "process": r"signal|SIGSEGV|segmentation fault|permission denied|avc: denied|child process",
    "steam": r"steamwebhelper|steam\.sh|gamescope|cef|exit code|fatal|error",
}
SECRET = re.compile(r"(?i)(token|password|authorization|cookie|sessionid)(\s*[:=]\s*)(\S+)")
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=pathlib.Path)
    ap.add_argument("--context", type=int, default=2)
    args = ap.parse_args()
    lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    matches = []
    for i, line in enumerate(lines):
        categories = [k for k, p in PATTERNS.items() if re.search(p, line, re.I)]
        if categories:
            matches.append((i, categories))
    selected = set()
    for i, _ in matches:
        selected.update(range(max(0, i-args.context), min(len(lines), i+args.context+1)))
    print(f"Scanned {len(lines)} lines; matched {len(matches)} lines.")
    for i in sorted(selected):
        clean = SECRET.sub(lambda m: m.group(1)+m.group(2)+"[REDACTED]", lines[i])
        print(f"{i+1:>6}: {clean}")
    print("\nCaution: review output for personal information before sharing.")
if __name__ == "__main__":
    main()
