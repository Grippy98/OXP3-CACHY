# Controller Tools: Xbox Wireless Adapter battery

Adds Xbox controller battery reporting to the Controller Tools Decky plugin when Linux uses the `xone` driver. The controller appears as **Xbox Wireless**, with **Low**, **Normal**, **High**, **Full** or **Unknown** and a matching battery icon. These are the levels the controller reports; they are not measured percentages.

**Status: installed and visually confirmed with one controller.** The frontend and backend build, 13 relevant Linux tests and 10 frontend/notification tests pass, and the installed API reports the real connected controller as wireless with `Normal` battery, matching sysfs. The user confirmed the plugin shows `Normal`. Two-controller hotplug and a physical low-battery alert remain to be checked. This folder contains a source patch and build instructions. It does not install a driver or modify the accepted kernel, controller mappings or power settings. Deploy both the Rust backend and frontend together.

## Requirements and scope

- Linux with Decky Loader and Controller Tools installed; the patch targets Controller Tools **2.0.2**, commit [`dcc05d953679c30b81ea3fb94a920af42fa3b44e`](https://github.com/jfernandez/ControllerTools/tree/dcc05d953679c30b81ea3fb94a920af42fa3b44e).
- A working `xone` gamepad driver. The tested source layout is xone **0.5.8**; its battery is exposed below `/sys/class/power_supply/` with `scope=Device` and `capacity_level`. A missing numeric `capacity` file is expected.
- A Linux build environment for the Rust backend and Node frontend. The helper checks its prerequisites; review missing dependencies before installing them.

This fixes plugin discovery and presentation. It does not add input support to an unpaired controller or recover telemetry the driver does not provide. Other controllers retain numeric percentages when their backend supplies them. The legacy Xbox Bluetooth error/zero ambiguity remains outside this change.

## Build

From the root of this repository:

```sh
bash fixes/controller-tools-xone-battery/build.sh
```

The helper prepares the pinned source and applies [patches/0001-xone-wireless-battery.patch](patches/0001-xone-wireless-battery.patch). The working tree is `build/controller-tools-xone-battery`; the deployment payload is `build/controller-tools-xone-battery/package/ControllerTools`. Build outputs stay outside this fix folder. The native build helper has not itself been run end-to-end on a second handheld. The source and modified plugin are covered by the included [GPLv3 license](LICENSE).

The source tests require Node **22.6+** and the locked dependencies. The backend test command intentionally skips the pinned upstream `settings::test::test_settings`, which assumes its read-only settings service creates and saves a file. That unrelated test fails in the original implementation; the battery tests are not skipped.

A read-only probe is also available after building:

```sh
build/controller-tools-xone-battery/package/ControllerTools/bin/backend --list-controllers
```

It prints the same controller model used by the API, without binding a port or changing input/power state. Serial numbers and internal sysfs paths are excluded.

## Install manually and reload this plugin

The collection menu links to this manual source build. For another installation:

1. Locate the existing `ControllerTools` plugin directory in Decky's configured plugin path. Back up the complete plugin payload to a separate folder **outside** the plugins directory. Retain its owner, modes and the corresponding settings; note the backup location for rollback.
2. Deploy the complete built `package/ControllerTools` payload to that same plugin directory. Preserve the separate Decky settings directory. Use staged file replacement for the executable rather than truncating the running `bin/backend`; partial frontend/backend updates are unsupported. Keep deployed code root-owned and executable only where required, and preserve the existing separate settings.
3. In **Decky → Settings → Plugins → Controller Tools → Reload**, reload only this plugin. Steam does not need to restart.

For an existing trusted Steam UI debugging session, the same Decky 3.3.0 action is:

```js
await DeckyBackend.callable('loader/reload_plugin')('Controller Tools')
```

The metadata name is **`Controller Tools`**, with a space; the directory is `ControllerTools`. The call queues a reload. Check the replacement backend and the updated plugin view after it completes. It stops the plugin's Rust child process, starts the new one and reloads the frontend. [Decky's reload action](https://github.com/SteamDeckHomebrew/decky-loader/blob/67196adfa9b299f20dfb0cc932e88a169417b7d5/frontend/src/components/settings/pages/plugin_list/index.tsx#L51).

## Check the result

- A paired controller has one entry with **Xbox Wireless**, its own battery level and no fabricated percentage or charging state.
- Two identical controllers on one adapter remain separate. Disconnecting one removes its entry without borrowing the other's battery reading.
- An idle adapter has no controller battery entry. A known wired Xbox controller without telemetry remains **Unknown**, rather than appearing full and charging.
- With notifications enabled, a discharging controller reporting **Low** can produce the existing rate-limited low-battery alert. **Normal**, **High**, **Full** and **Unknown** do not produce a low alert. A real low-battery transition still needs hardware verification.

`Normal` may persist for a long time: the driver reports a range, not a continuously changing percentage. Missing or unrecognized data remains unknown. See [WRITEUP.md](WRITEUP.md) for the protocol limit, matching rules and validation boundaries.

## Roll back

Restore the complete backed-up plugin payload, preserving its owner and modes, then use the same **Controller Tools → Reload** action. Restore frontend and backend together. Keep the existing settings unless intentionally reverting a separate settings change. A future plugin-store update can replace this local patch; rebase/rebuild before reapplying it to another version.
