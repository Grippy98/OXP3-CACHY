# Moonlight client: Native display, bitrate and DualSense haptics

This is a manual source-build guide for the Intel OXP3 on CachyOS. It links the integrated client in [Grippy98/moonlight-qt](https://github.com/Grippy98/moonlight-qt), branch [feature/oxp3-dualsense-waveform](https://github.com/Grippy98/moonlight-qt/tree/feature/oxp3-dualsense-waveform), pinned at [`9003439366f8c566d938b5625bad1e2e6f8dc11c`](https://github.com/Grippy98/moonlight-qt/commit/9003439366f8c566d938b5625bad1e2e6f8dc11c). It retains the Native display, network bitrate and optional Intel import work on Nonary's waveform-capable Moonlight base. The collection menu opens these instructions; it does not build or install Moonlight.

**Status:** the integrated Linux HDR/4:4:4 client built and is installed as the native preview. Native/bitrate/launcher checks, QML parsing and the haptics renderer suite pass. The owner confirmed a controlled local waveform test felt distinct left-then-right feedback on the Bluetooth DualSense. A Windows stream through the updated Steam shortcut works and redetects the controller after Bluetooth reconnect. During gameplay, a passive Bluetooth check verified nonzero waveform output on both actuator channels, alongside successful adaptive-trigger commands. The earlier client passed docked production display detection and offscreen Intel decode/import/color checks; those are historical results, not fresh display validation of this build. Physical undock/reconnect and actual HDR presentation remain unverified.

## DualSense waveform setup

Pair a DualSense or DualSense Edge to the Linux client over **Bluetooth**. SDL must see the physical PlayStation controller, and the session user needs read/write access to its `hidraw` node. Existing device rules may already provide this; do not grant access to every HID device or run Moonlight as root.

The installed **Moonlight** Steam shortcut now launches this native preview, with **Disable Steam Input** selected for that shortcut. Fresh native Steam details confirmed both changes. For another installation, point the shortcut at the integrated client and select **Properties → Controller → Disable Steam Input**, so Steam does not present a virtual Xbox controller in place of the DualSense. Keep this override scoped to Moonlight; the OXP3's built-in controller integration does not need to be disabled.

For a **Windows Vibepollo host**:

1. Install Vibepollo's optional **DualSense USB audio and haptics** component.
2. Select **DualSense with waveform haptics** (`usbip_ds5`), or Automatic PlayStation selection with that transport available. A conventional virtual DualSense alone does not supply its USB audio haptic endpoint.
3. Reconnect the stream, then use a game with native DualSense haptics. Disable Steam Input for that host game when it would translate the controller instead of exposing native DualSense support.

See Vibepollo's [Windows setup and validation](https://github.com/Nonary/Vibepollo/blob/master/docs/windows-dualsense-haptics.md). USB/IP is local to the Windows host; no USB/IP driver is required on the OXP3. Linux hosts have a separate [composite DS5 setup](https://github.com/Nonary/Vibepollo/blob/master/docs/linux/playstation-controllers.md).

The client should report **DualSense Bluetooth waveform backend ready** and advertise waveform capability `0x8000` for that controller. These establish backend attachment/negotiation, not felt playback. Bluetooth output is signed **8-bit stereo at 3 kHz**: native waveform haptics, with different fidelity from the 48 kHz USB path. Ordinary rumble or adaptive triggers alone do not establish waveform playback. Controller speaker and microphone streaming are outside this Linux renderer.

Test distinct left/right effects, input during feedback, adaptive triggers, idle, Bluetooth reconnect and stream exit. The pinned [haptics test guide](https://github.com/Grippy98/moonlight-qt/blob/9003439366f8c566d938b5625bad1e2e6f8dc11c/tests/haptics/README.md) separates deterministic renderer tests from physical validation. The installed `moonlight --haptics-license` prints the embedded SAxense source and license notices. A `--version` value alone does not identify this fork or prove waveform support.

## What the options do

- Select **Native (Follow display)** independently for resolution and FPS. Each stream start reads the current active display mode, including a read-only physical-output query under Gamescope. It uses the configured mode, rather than the display's maximum advertised mode. Reconnect after docking or undocking; an existing stream is not renegotiated. Fractional refresh rates round to the nearest protocol FPS, such as 143.99 Hz to 144 FPS.
- Fixed/custom values are retained while Native is selected. Ambiguous or unavailable physical-output information falls back to the selected desktop display; missing/invalid discovery retains the saved fixed value. The streaming host must accept the requested mode.
- **Use a separate bitrate for Wi-Fi** selects a preset using the route to the streaming host when connecting. Confirmed non-VPN Ethernet uses the primary rate; Wi-Fi, VPN and unknown routes use the Wi-Fi preset. This is preset selection, not bandwidth measurement or live adaptation.
- Moving a bitrate slider makes that rate manual. Conventional-codec automatic primary rates follow the resolved mode and normal/unlocked bitrate limits; PyroWave retains its codec-specific automatic rate. Explicit primary, CLI and Wi-Fi preset values are preserved.

See the pinned [client guide](https://github.com/Grippy98/moonlight-qt/blob/9003439366f8c566d938b5625bad1e2e6f8dc11c/docs/oxp3-cachyos.md) for fallback behavior, CLI precedence, prerequisites and test commands, and the [writeup](WRITEUP.md) for implementation and limits.

## Build and run a separate preview

Run these commands as the normal desktop user on CachyOS. The build helper checks prerequisites; it does not install packages or replace system libraries. Review missing prerequisites in the pinned client guide.

```sh
git clone --branch feature/oxp3-dualsense-waveform https://github.com/Grippy98/moonlight-qt.git
cd moonlight-qt
git checkout 9003439366f8c566d938b5625bad1e2e6f8dc11c
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

Use HEVC for Intel 4:4:4 testing. The build compiles Moonlight against a private header override; it leaves the installed libplacebo shared library unchanged. The pinned [prototype source and instructions](https://github.com/Grippy98/moonlight-qt/tree/9003439366f8c566d938b5625bad1e2e6f8dc11c/contrib/intel-packed-yuv444) retain the libplacebo source pin, patch, licenses and reusable tests. They are not duplicated here.

The earlier import prototype passed offscreen Intel decoding and GPU import for 8-bit and 10-bit HEVC 4:4:4. Actual compositor/swapchain HDR presentation, TV signaling, full-resolution throughput and gameplay pacing need separate verification on this integrated client. These changes do not resolve the collection's [experimental HDMI VRR](../external-display-vrr/README.md) or [CEC transport](../hdmi-cec/README.md) limitations.

## Verify and roll back

Check Native selection at stream start, first with a fixed known-good display mode. Compare primary and Wi-Fi rates using the actual route to the host. Reconnect after changing the physical display; physical undock/reconnect is a remaining hardware test, not an established outcome. The pinned client guide provides host policy/launcher tests and a read-only production display-detector probe. HDR requires a separate visible stream test, beyond the offscreen import checks.

Deployment retains a private backup of the original native runtime, preview profile and Steam shortcut metadata. To roll back, quit the preview and restore the relevant backed-up runtime/profile, or launch the original Moonlight Flatpak. If a Steam shortcut is retargeted to the preview, restore its original executable, start directory, launch options and Steam Input override through Steam's Properties UI. Keep the original Flatpak installed. The source build does not retarget a Steam shortcut automatically.

Select the standard build to compare without the HDR/4:4:4 override. After closing the preview, its build outputs and dedicated private state directory can be removed if desired. Removing private state discards its copied pairing identity/preferences; a new preview will import again on first launch. No configuration is copied back to the Flatpak.
