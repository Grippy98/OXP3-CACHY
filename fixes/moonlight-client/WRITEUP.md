# Moonlight implementation and upstream direction

## Problem and source boundary

A handheld can use different display sizes and refresh rates when docked and undocked. Moonlight's saved fixed resolution/FPS and a single bitrate can require repeated adjustment. Separately, Linux Intel HEVC 4:4:4 decode support does not by itself guarantee that the decoded surfaces can reach the renderer: the packed DMA-BUF layout also needs a compatible import path.

The implementation lives in [Grippy98/moonlight-qt at bd009697190f2c1e012afaeaa7ed1ef4ea27170a](https://github.com/Grippy98/moonlight-qt/tree/bd009697190f2c1e012afaeaa7ed1ef4ea27170a), on branch [feature/oxp3-native-display-hdr444](https://github.com/Grippy98/moonlight-qt/tree/feature/oxp3-native-display-hdr444). This collection contains documentation and a manual menu entry only. It carries no duplicate client source, adapter patch, application binary, profile or hardware capture.

The client pin retains the fork's existing network-aware bitrate work on top of upstream Moonlight commit `dc92b6d2f361064d3e9e53ce5de92f611db77220`. Submodules remain fixed by that checkout's gitlinks. Build and private-profile rollback instructions are in the [README](README.md) and pinned [client guide](https://github.com/Grippy98/moonlight-qt/blob/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/docs/oxp3-cachyos.md).

## Native resolution and FPS

Two independent saved booleans select display-following resolution and FPS. Fixed/manual values stay saved as fallback values. The session resolves Native once at each connection start, before choosing its automatic primary bitrate. It does not change the local display mode or renegotiate an already-running stream.

Under Gamescope, the desktop display may describe the virtual game-sized surface. A read-only DRM query enables atomic property access and looks for a single active physical output, ignoring a connected but disabled built-in panel. Multiple active outputs or incomplete/inaccessible DRM information fall back to the selected desktop display. Invalid discovery retains the corresponding fixed preference. Current timing provides the refresh rate, rounded to the nearest integer required by the streaming protocol.

The client cannot guarantee that a host accepts the requested dimensions, codec or rate, and it does not provision a host virtual display. Detection tests and a successful docked production-object probe support the selection logic; they do not establish physical undock/reconnect behavior or a game's pacing.

## Network-aware bitrate

The checkbox enables a second saved bitrate. Selection uses the socket route to the streaming host at connection start. Only positively identified non-VPN Ethernet selects the primary preset; Wi-Fi, VPN and unknown routes select the Wi-Fi preset. Ethernet can therefore be selected while an unrelated Wi-Fi connection remains up. This does not measure available throughput or continuously adapt the rate.

The shared runtime policy keeps explicit primary/Wi-Fi values intact. Automatic primary defaults use the resolved dimensions, FPS and chroma, then clamp to 500–150000 Kbps, or a 500000 Kbps maximum when unlocked. Slider changes and `--bitrate` select a manual primary rate. `--wifi-bitrate` enables the separate preset; `--bitrate` alone disables a saved network-aware selection. A host fallback from 4:4:4 to 4:2:0 recomputes only an automatic primary rate, preserving manual and Wi-Fi values.

CLI Native and fixed options update their respective setting independently; the last conflicting option of each type wins. Pure policy tests exercise route classification, manual values, selected presets and automatic bounds through the same helpers used by the client.

## Opt-in Intel packed-surface import

The [candidate and technical writeup](https://github.com/Grippy98/moonlight-qt/blob/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/contrib/intel-packed-yuv444/WRITEUP.md) target libplacebo **v7.360.1**, commit `cee9b076f2c63104ccfd497fa79c39a867293ec4`. Moonlight compiles that library's header-only FFmpeg adapter, so rebuilding this object against a private patched header is sufficient. The build checks the exact shared-library version and input-header hashes, leaving installed headers and the shared library unchanged.

For supported Vulkan imports, packed XYUV uses a bit-identical BGRA8 alias, and Y410/XV30 use RGB10A2 aliases. Channel mappings retain YUV interpretation, bit depth and color metadata. Known unsupported layer/plane layouts and failed imports are refused. The candidate preserves VAAPI decoding and GPU rendering; it adds no streaming-frame CPU download or runtime software-decoding fallback. It still relies on FFmpeg/driver descriptor validity as the original adapter does.

Regression coverage includes packed descriptor mappings, unsupported layouts, failed-import cleanup, source immutability, GPU channel/color arithmetic and software test oracles. A separate offscreen Intel hardware probe forces VAAPI decode and direct DMA-BUF/Vulkan import for 8-bit and 10-bit HEVC 4:4:4. The CPU reference is a test oracle only. Successful small offscreen packets establish interoperability for those layouts; they do not prove visible HDR presentation or full-resolution streaming throughput.

## Validation limits and rollback

The client has a native CachyOS build, production docked display-detector validation, Native/bitrate policy tests, private-launcher tests and QML parsing checks. The import prototype has offscreen real Intel validation. Physical undock/reconnect, compositor HDR/swapchain negotiation, TV HDR signaling, 4K/144 Hz HDR/4:4:4 performance and gameplay pacing remain separate tests. No HDMI link, VRR or CEC support is implied.

The private launcher copies the installed Flatpak's configuration only when a preview profile is absent, preserving pairing identity and key casing. It initially changes only the two Native preference values. Private permissions, linked/unowned path refusals and argument forwarding are covered by launcher regressions. Later launches retain preview edits, and nothing is copied back. Quitting the preview and returning to the original Flatpak is the application rollback; selecting a standard build removes the adapter prototype from the comparison.

## Upstream targets and licenses

Native display selection, CLI/settings behavior and network-aware bitrate changes belong in Moonlight, with policy tests and platform fallbacks reviewed there. The packed import belongs in libplacebo's FFmpeg adapter; related primary reports are [libplacebo issue 282](https://github.com/haasn/libplacebo/issues/282) and [Moonlight issue 1512](https://github.com/moonlight-stream/moonlight-qt/issues/1512). The exact pinned adapter candidate should be reviewed/rebased for other libplacebo versions before broadening its build support.

Moonlight retains its [GPL-3.0 license](https://github.com/Grippy98/moonlight-qt/blob/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/LICENSE). The candidate adapter patch retains [libplacebo's LGPL-2.1-or-later license](https://github.com/Grippy98/moonlight-qt/blob/bd009697190f2c1e012afaeaa7ed1ef4ea27170a/contrib/intel-packed-yuv444/LICENSE.libplacebo). Source, pins, attribution and reusable tests remain with the linked implementation; this entry makes no upstream submission or change to those licenses.
