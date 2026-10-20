# Intel TDP controls and MangoHud telemetry

Three independent components for the Intel ONEXPLAYER 3 on CachyOS/Deckify:

| Component | What it fixes | Install |
| --- | --- | --- |
| [TDP](tdp/INSTALL.md) | Steam performance slider through SteamOS Manager; verified writes to both Intel RAPL interfaces | `sudo ./install.sh tdp --session-user "$USER"` |
| [Read permissions](permissions/README.md) | Lets members of `video` read the selected package, graphics and temperature sensors | `sudo ./install.sh permissions` |
| [MangoHud](telemetry/README.md) | Graphics watts, real GPU temperature, shared process GPU memory, and upstream MangoApp render-loop backport | Build the pinned package; installation requires an explicit package path |

Run commands from this directory. The TDP installer uses `$SUDO_USER` when `--session-user` is omitted. It requires a logged-in non-root desktop session, native `steamos-manager` and `python-dbus-next`. Metrics permissions require the existing `video` group; group membership is managed separately. These scripts check the device, dependencies and destination parents before changing system files, retain backups, and refuse to overwrite an active installation record.

The configured Steam slider is **8–40 W**. The manufacturer's [global page](https://onexplayerstore.com/products/onexplayer-3-next-gen-3-in-1-ai-gaming-and-productivity-handheld) advertises **8–35 W**; its [Japanese page](https://www.onexplayer.online/onexplayer-3) documents an optional **40 W** endpoint. This is device policy, not a measured BIOS adjustment range. A request sets package PL1 and PL2 in both MSR and MMIO; start alone changes no power limits. Graceful service stop restores the fresh baseline. Steam's checkbox has no separate restore operation in the remote API.

Package watts include the integrated GPU; do not add GPU watts to package watts. GPU memory means current-process shared memory, not dedicated VRAM or total system allocation. Intel PMT temperature is decoded only for the exact supported GUID and size. Missing access or unsupported sensors remain unavailable. The MangoApp backport alone does not resolve every Gamescope frame-cap issue.

See [rollback](ROLLBACK.md) and [source credits](telemetry/CREDITS.md). Source, patches, tests and third-party licenses are included; compiled packages and device logs are excluded.
