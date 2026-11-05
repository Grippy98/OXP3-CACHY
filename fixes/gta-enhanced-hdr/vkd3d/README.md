# Preserve every D3D12 fence-event registration

This per-game vkd3d-proton update preserves duplicate fence-event registrations. **HDR with XeSS SR reached Story Mode on two short cold-start tests** using the Core-only method below, private Mesa 26.3 and the private WSI candidate. Frame generation remains unqualified: native FSR FG flickered, and Intel XeFG failed a separate swapchain-lifetime test. An initial full DLL-pair trial had HDR inactive and is not an HDR qualification.

Older vkd3d-proton drops a repeated `SetEventOnCompletion()` registration for the same fence value and event handle. Two threads waiting on that auto-reset event then receive only one signal. Upstream removed this suppression in [commit 49a1e2c](https://github.com/HansKristian-Work/vkd3d-proton/commit/49a1e2c7098f4646374458b9a8fbc7c0d0b5ff3d); the change is included in the official stable [v3.1 release](https://github.com/HansKristian-Work/vkd3d-proton/releases/tag/v3.1).

The upstream report concerns The Witcher 3. It does not establish that every GTA loading freeze, HDR problem, or upscaling problem has this cause.

## Install for this ReShade configuration

The [checked installer](INSTALLER.md) provides per-game install/check/rollback commands. It changes only the Core file; the launch preference below remains a separate step.

Close the game before changing its files. This Core-only method is verified at source level for the inspected Experimental loader (`cae2e003…`) and official v3.1 Core. The loader and its private Core interface have no source differences between those pins. Recheck compatibility before applying the method to a substantially different loader.

1. Download the official `vkd3d-proton-3.1.tar.zst` release linked above. Verify the archive and x64 DLL hashes in [source-pins.json](source-pins.json).
2. Back up any existing `d3d12core.dll` beside the game's executable, preserving its original name. Record a missing file as missing; check for case variants.
3. Put **only `x64/d3d12core.dll`** beside the game's executable. Preserve the original system32 `d3d12.dll` loader so ReShade keeps intercepting device creation there.
4. Add `d3d12core=n,b` to that game's `WINEDLLOVERRIDES` value, retaining its other overrides. A game with no existing override can use `WINEDLLOVERRIDES="d3d12core=n,b" %command%` in Steam launch options. Existing wrappers should merge the entry instead.

If an earlier diagnostic placed the release's `d3d12.dll` beside the executable, restore its exact previous state from that diagnostic's manifest. Remove it only when its recorded original state was missing and its hash still matches the diagnostic file. Do not remove an unrelated mod's DLL.

The original loader uses `LoadLibraryA("d3d12core.dll")` before its explicit system32 fallback. The game-directory Core is therefore eligible without modifying the prefix or shared Proton installation. Confirm the actual loaded paths during validation.

The full release DLL pair remains the normal upstream deployment method for configurations without this hook-location constraint. Putting a new `d3d12.dll` in the game directory can bypass ReShade 6.8's default system32 D3D12 hook target and disable a RenoDX HDR addon. A menu that loads with HDR inactive is not a valid HDR comparison.

Do not run `setup_vkd3d_proton.sh` for this per-game method: it installs into the prefix and writes persistent registry overrides.

## Check and undo

Confirm that the game loads the original system32 D3D12 loader and the staged game-directory Core, and that vkd3d reports the new source build. Confirm ReShade proxies the D3D12 device, RenoDX initializes on D3D12, and HDR remains active; a mapped ReShade module alone is insufficient. Keep the Mesa version, game resolution, HDR state, and actual scaling setting consistent. A driver-name change can reset GTA's scaling option. Recheck Story loading, image quality, menus, and controls; qualify frame generation and HUD separately.

To undo, close the game, remove the staged Core, and restore its exact backed-up file state. Remove only this fix's native-preference entry from the game's environment. The shared Proton installation and other games need no changes.

## Intel XMX compatibility

The community XMX shim creates ordinary D3D12 root signatures, compute pipelines, and command queues. No new private vkd3d ABI or SDK flag is required by this update. Retain the existing scoped `VKD3D_DISABLE_EXTENSIONS=VK_EXT_descriptor_buffer,VK_KHR_present_wait2` restriction used by that shim. Its placeholder self-test and actual XeSS initialization/dispatch still need to pass; do not bypass its self-test to force XMX.

See [WRITEUP.md](WRITEUP.md) for provenance, limitations, and licensing. This folder contains installer source, tests, documentation and an upstream patch, with no game files or release binaries.
