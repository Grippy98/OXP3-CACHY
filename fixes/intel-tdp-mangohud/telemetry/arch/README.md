# Native Arch/CachyOS package

Build on native x86-64 Linux as the desktop user. Install `base-devel` and the `makedepends` in `PKGBUILD` first; this recipe does not refresh package databases or install dependencies.

```sh
makepkg --cleanbuild
```

The recipe pins MangoHud v0.8.4 commit `992103e4fb744897826de04ea00a2f71e7018214`, both patches, helper tests and seven Meson archives/patch archives by commit/hash. Meson rechecks cached wrap hashes and `--wrap-mode=nodownload` prevents configure/build downloads. Initial source retrieval requires network access.

Builds default to four compile jobs. Set `ONEX3_BUILD_JOBS` to a positive integer to change that limit. Build inputs are fixed; identical binary output additionally depends on toolchain, dependencies and makepkg flags.

`mangohud-onex3` provides `mangohud=0.8.4` and `mangoapp`, and conflicts with the listed 64-bit distribution packages. It builds `/usr/lib/mangohud`, MangoApp and mangohudctl with bundled spdlog and XNVCtrl disabled. It does not replace `lib32-mangohud`, install sensor permissions, or change power settings.

Before installing, preserve a cached package archive for every installed package that pacman will replace. Inspect installed packages with `pacman -Q | rg '^(mangohud|mangoapp)'`, then copy their matching versioned archives from `/var/cache/pacman/pkg` to your own backup directory. If a matching archive is unavailable, obtain it from your distribution's archive before replacing the package. Install only an explicit built output:

```sh
sudo pacman -U /absolute/path/to/mangohud-onex3-0.8.4-3-x86_64.pkg.tar.zst
```

Review pacman's transaction, then restart MangoApp or the gaming session. Reinstall the saved original archive(s) with `pacman -U` to roll back. The included MangoApp render-loop fix alone does not solve every Gamescope frame-cap issue.

The local patch/test copies must stay byte-identical to `../mangohud-intel-telemetry.patch`, `../mangoapp-one-render-per-frame.patch` and `../tests/`. Their SHA256 values are in `PKGBUILD`; attribution and licenses are in [CREDITS.md](../CREDITS.md).
