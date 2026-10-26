#!/usr/bin/env bash
set -euo pipefail
# Build on native aarch64 GitHub runner. No Android root access is needed.
out="${1:?output tar path required}"
work="$(mktemp -d)"
trap 'sudo umount -lf "$work/root/dev" 2>/dev/null || :; sudo umount -lf "$work/root/proc" 2>/dev/null || :; sudo umount -lf "$work/root/sys" 2>/dev/null || :; sudo rm -rf "$work"' EXIT
mirror="https://ca.us.mirror.archlinuxarm.org/os"
curl -fL --retry 3 "$mirror/ArchLinuxARM-aarch64-latest.tar.gz" -o "$work/arch.tar.gz"
curl -fL --retry 3 "$mirror/ArchLinuxARM-aarch64-latest.tar.gz.md5" -o "$work/arch.tar.gz.md5"
(cd "$work" && sed "s|ArchLinuxARM-aarch64-latest.tar.gz|arch.tar.gz|g" arch.tar.gz.md5 | md5sum -c -)
mkdir -p "$work/root"
sudo tar -xzf "$work/arch.tar.gz" -C "$work/root"
# GitHub Ubuntu uses a systemd-resolved loopback stub that is not available in chroot.
# Use the runner's real upstream resolver configuration, not 127.0.0.53.
sudo rm -f "$work/root/etc/resolv.conf"
if [ -s /run/systemd/resolve/resolv.conf ]; then
  sudo cp /run/systemd/resolve/resolv.conf "$work/root/etc/resolv.conf"
else
  sudo cp /etc/resolv.conf "$work/root/etc/resolv.conf"
fi
# The rootfs default mirror hostname may not resolve; use the same HTTPS mirror
# that successfully supplied the verified ARM64 bootstrap.
sudo mkdir -p "$work/root/etc/pacman.d"
printf 'Server = https://ca.us.mirror.archlinuxarm.org/$arch/$repo\n' | sudo tee "$work/root/etc/pacman.d/mirrorlist" >/dev/null
echo 'Chroot DNS:'
sudo cat "$work/root/etc/resolv.conf"
echo 'Arch mirror:'
sudo cat "$work/root/etc/pacman.d/mirrorlist"
for d in dev proc sys; do sudo mount --bind "/$d" "$work/root/$d"; done
# Pacman's CheckSpace cannot resolve mount points inside this GitHub runner chroot.
# Disable that check only here; verify available host disk space explicitly.
df -h "$work"
sudo sed -i 's/^[[:space:]]*CheckSpace[[:space:]]*$/#CheckSpace/' "$work/root/etc/pacman.conf"
# Use the package manager inside an actual Arch Linux ARM environment.
sudo chroot "$work/root" /bin/bash -lc 'pacman-key --init && pacman-key --populate archlinuxarm && pacman -Syu --noconfirm --needed vulkan-swrast vulkan-tools'
sudo test -n "$(sudo find "$work/root/usr/share/vulkan/icd.d" -name 'lvp_icd*.json' -print -quit)"
# Bundle only installed package payloads, including dependent libraries, not the entire OS.
sudo chroot "$work/root" /bin/bash -lc 'pacman -Qq' > "$work/base-packages.txt"
# The bundle contains Vulkan loader, Mesa, LLVM and dependent libraries; all ARM64.
# Extracting into the r9 Arch guest is experimental until ABI compatibility is verified.
sudo chroot "$work/root" /bin/bash -lc 'pactree -u vulkan-swrast 2>/dev/null || echo vulkan-swrast' > "$work/deps.txt"
printf '%s\n' vulkan-swrast vulkan-icd-loader mesa llvm-libs libdrm libelf zstd libx11 libxcb libxshmfence libxxf86vm wayland > "$work/selected.txt"
: > "$work/paths.txt"
while IFS= read -r pkg; do
  sudo chroot "$work/root" /usr/bin/pacman -Qlq "$pkg" 2>/dev/null | sed 's|^/||' >> "$work/paths.txt" || :
done < "$work/selected.txt"
sort -u "$work/paths.txt" -o "$work/paths.txt"
sudo tar -cf "$out" -C "$work/root" --no-recursion -T "$work/paths.txt"
test -s "$out"
echo "Lavapipe ARM64 archive: $(du -h "$out")"
