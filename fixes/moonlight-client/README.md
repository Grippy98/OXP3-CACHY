# Moonlight client: Native display and bitrate options

This is a manual source-build guide for the Intel OXP3 on CachyOS. It links the client changes in [Grippy98/moonlight-qt](https://github.com/Grippy98/moonlight-qt), branch [feature/oxp3-native-display-hdr444](https://github.com/Grippy98/moonlight-qt/tree/feature/oxp3-native-display-hdr444), pinned at [`bd009697190f2c1e012afaeaa7ed1ef4ea27170a`](https://github.com/Grippy98/moonlight-qt/commit/bd009697190f2c1e012afaeaa7ed1ef4ea27170a). The collection menu opens these instructions; it does not build or install Moonlight.

**Status:** the native client builds, its docked production display detector has been checked, and the optional Intel import path passed real offscreen decode/import/color checks. Physical undock/reconnect behavior and actual HDR presentation remain unverified. A successful import test does not establish 4K/144 Hz HDR/4:4:4 streaming performance.

## What the options do

- Select **Native (Follow display)** independently for resolution and FPS. Each stream start reads the current active display mode, including a read-only physical-output query under Gamescope. It uses the configured mode, rather than the display's maximum advertised mode. Reconnect after docking or undocking; an existing stream is not renegotiated. Fractional refresh rates round to the nearest protocol FPS, such as 143.99 Hz to 144 FPS.
- Fixed/custom values are retained while Native is selected. Ambiguous or unavailable physical-output information falls back to the selected desktop display; missing/invalid discovery retains the saved fixed value. The streaming host must accept the requested mode.
- **Use a separate bitrate for Wi-Fi** selects a preset using the route to the streaming host when connecting. Confirmed non-VPN Ethernet uses the primary rate; Wi-Fi, VPN and unknown routes use the Wi-Fi preset. This is preset selection, not bandwidth measurement or live adaptation.
- Moving a bitrate slider makes that rate manual. Automatic primary rates follow the resolved mode and normal/unlocked bitrate limits; explicit primary, CLI and Wi-Fi preset values are preserved.

See the pinned [client guide](https://github.com/Grippy98/moonlight-qt/blob/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/docs/oxp3-cachyos.md) for fallback behavior, CLI precedence, prerequisites and test commands, and the [writeup](WRITEUP.md) for implementation and limits.

## Build and run a separate preview

Run these commands as the normal desktop user on CachyOS. The build helper checks prerequisites; it does not install packages or replace system libraries. Review missing prerequisites in the pinned client guide.

```sh
git clone --branch feature/oxp3-native-display-hdr444 https://github.com/Grippy98/moonlight-qt.git
cd moonlight-qt
git checkout bd009697190f2c1e012afaeaa7ed1ef4ea27170a
git submodule update --init --recursive
bash scripts/build-cachyos-oxp3.sh --check
bash scripts/build-cachyos-oxp3.sh
bash scripts/run-cachyos-oxp3.sh
```

The default binary is `build/oxp3/app/moonlight`. The launcher uses a separate profile under `$XDG_DATA_HOME/moonlight-oxp3-preview` (normally `~/.local/share/moonlight-oxp3-preview`). On its first launch, it imports the installed Moonlight Flatpak configuration if available, preserving its pairing identity and host list while initially enabling the two Native options. Otherwise, pair this client normally. Subsequent launches retain the preview's preferences.

The original Flatpak and its profile remain available. Run one client at a time. The private preview profile contains pairing credentials and belongs outside either source repository. `MOONLIGHT_OXP3_STATE_DIR` can select another dedicated private state directory; do not point it at the installed application's profile.

Optional CLI examples, using a host and app already known to Moonlight:

```sh
bash scripts/run-cachyos-oxp3.sh stream --native-resolution --native-fps HOST APP
bash scripts/run-cachyos-oxp3.sh stream --native-resolution --native-fps \
  --bitrate 120000 --wifi-bitrate 35000 HOST APP
```

## Optional Intel HDR / 4:4:4 prototype

Start with the ordinary build above. This opt-in build addresses packed Intel VAAPI surface import into libplacebo's Vulkan renderer. It requires **exactly libplacebo 7.360.1**, plus the exact unmodified source headers checked by the preparation script. Review/rebase for another library version instead of bypassing the checks.

```sh
bash scripts/build-cachyos-oxp3.sh --check --hdr444
bash scripts/build-cachyos-oxp3.sh --hdr444 build/oxp3-hdr444
MOONLIGHT_OXP3_BINARY="$PWD/build/oxp3-hdr444/app/moonlight" \
  bash scripts/run-cachyos-oxp3.sh
```

Use HEVC for Intel 4:4:4 testing. The build compiles Moonlight against a private header override; it leaves the installed libplacebo shared library unchanged. The pinned [prototype source and instructions](https://github.com/Grippy98/moonlight-qt/tree/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/contrib/intel-packed-yuv444) retain the libplacebo source pin, patch, licenses and reusable tests. They are not duplicated here.

Offscreen Intel decoding and GPU import have passed for 8-bit and 10-bit HEVC 4:4:4. Actual compositor/swapchain HDR presentation, TV signaling, full-resolution throughput and gameplay pacing need separate verification. These changes do not resolve the collection's [experimental HDMI VRR](../external-display-vrr/README.md) or [CEC transport](../hdmi-cec/README.md) limitations.

## Verify and roll back

Check Native selection at stream start, first with a fixed known-good display mode. Compare primary and Wi-Fi rates using the actual route to the host. Reconnect after changing the physical display; physical undock/reconnect is a remaining hardware test, not an established outcome. The pinned client guide provides host policy/launcher tests and a read-only production display-detector probe. HDR requires a separate visible stream test, beyond the offscreen import checks.

To roll back, quit the preview and launch the original Moonlight Flatpak or its existing Steam shortcut. Select the standard build to compare without the HDR/4:4:4 override. After closing the preview, its build outputs and dedicated private state directory can be removed if desired. Removing private state discards its copied pairing identity/preferences; a new preview will import again on first launch. No configuration is copied back to the Flatpak.
