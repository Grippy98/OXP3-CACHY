# Manual kernel build

This is a research build recipe, not a kernel installer. Linux, kernel build dependencies, LLVM 19, pahole, Python 3, kmod and zstd are required. An ARM64 Linux host may cross-compile with `ARCH=x86_64 LLVM=-19`; use those values for every Kbuild invocation. No particular Docker container, volume or `/build` path is required.

Use the pinned CachyOS source and distribution inputs in [SOURCES.md](SOURCES.md). Apply the matching acpi-call, handheld and BORE patches as in that recipe, then the adjacent EDID patch. One AMD 420-only handheld hunk was already implemented in the tested source; inspect it rather than blindly forcing a rejected hunk.

```sh
# Set repo and tree to absolute paths in your own Linux build workspace.
cp "$repo/fixes/lg-c5-edid/kernel/configs/test.config" "$tree/.config"
cd "$tree"
git apply --check "$repo/fixes/lg-c5-edid/kernel/edid-segment-reset-retry.patch"
git apply "$repo/fixes/lg-c5-edid/kernel/edid-segment-reset-retry.patch"
make ARCH=x86_64 LLVM=-19 olddefconfig
make ARCH=x86_64 LLVM=-19 -j"$(nproc)" bzImage modules
```

The supplied config is the tested OXP3-specific reduced config, with release `7.2.9-onex3-edid-test`. It is not a universal laptop config. It retains Xe display, NVMe/Btrfs, handheld HID, USB-C/Thunderbolt, network, audio and sched_ext/BTF; Rust and panic QR output are disabled. Audit peripheral support for your hardware. `../scripts/restore-test-drivers.py` documents the original config restoration choices; it requires a full original config and is not needed when using this final config.

For the **full accepted internal-panel kernel**, use [the panel build workflow](../../internal-panel-refresh/kernel/README.md), which additionally preserves the controller override and InputPlumber transports. The EDID-only historical kernel is not the recommended replacement for that accepted runtime. No prebuilt kernel, target initramfs, boot entry, signing key or automatic installation script is included.
