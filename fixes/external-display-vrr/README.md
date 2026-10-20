# Experimental Intel dock-to-HDMI VRR

See [WRITEUP.md](WRITEUP.md) for the technical explanation and upstream scope.

**Manual research only; excluded from default installation.** The FreeSync-over-GMP revision 3 prototype has one narrow owner-confirmed stable result: the UGREEN Steam Deck Dock 6-in-1 and LG C5 sustained FreeSync near 80 Hz with a steady 80 FPS workload at **1080p120 SDR**. The owner also reported positive 60/80 FPS sweep segments; 100 FPS produced black dropped frames and remains unresolved.

| Tested configuration | Status |
| --- | --- |
| 1080p120 SDR, steady 80 FPS, FreeSync/GMP v3 | Owner confirmed stable FreeSync near 80 Hz |
| 1080p SDR, sweep 60/80 FPS | Positive owner report |
| 1080p SDR, 100 FPS | Black/dropped frames; steady-rate physical result unresolved |
| 3840×2160 fixed 120 Hz SDR, VRR off | Picture works |
| 4K120 VRR, input 10 bpc / DSC 10 bpp | Correct AS/GMP/PPS/timing-generator state, TV briefly 120 then black |
| 4K120 VRR, input 8 bpc / DSC 10 bpp | GPU source counter near 80 Hz; physical TV behavior unconfirmed |
| 4K VRR / HDR | **No working fix claimed** |

Correct GPU packet/readback state and an application/source counter are insufficient to prove the physical TV refresh. Startup HDR/VRR Invalid Format, rate transitions, broad VRR range, reconnect/power-cycle behavior and other docks remain open. No device changes or promotion are performed by this package.

## What the patches do

The Intel shared display code rejects DP branch VRR, and this converter lacks advertised MSA timing-ignore support. The local [AS SDP v1 patch](intel-pcon-vrr-experimental.patch) adds opt-in capability checks and revision-1 packet packing/readback. `enable_pcon_vrr=0` preserves the original path; `1` requires normal HDMI/FRL/MSA capabilities; `2` additionally permits the exact observed `90:cc:24` / `cHDMIb` converter with its misleading downstream-port descriptor. MST is excluded. The exception is not a general UGREEN or chip-family quirk.

Apply [the upstream VTotal backport](intel-vrr-mode-vtotal-f26a8df.patch) next. It retains actual VTotal in transcoder/MSA timing rather than the placeholder 1. This repaired the GPU state but did not independently produce a usable TV picture in the AS-only candidate.

Apply [FreeSync-over-GMP v3](freesync-gmp/README.md) last for the limited positive SDR configuration. It sends AMD's vendor SDP through Intel's DP-capable GMP slot alongside AS SDP v1. It requires the exact converter identity, an AMD v2 CTA capability/range, active VRR and verified SDR/default colorspace. The advertised AMD range must cover the complete active Intel timing-generator range. HDR uses that slot too; this prototype does not combine HDR and FreeSync in GMP.

Both experimental parameters default off. For an explicitly controlled, separately named **Xe** test boot only, v3 uses `xe.enable_pcon_vrr=2 xe.pcon_freesync_sdp=1`; an i915 system uses the `i915.` prefix. No installer writes these parameters or changes a boot default. Keep the accepted `7.2.9-onex3-vrr-test` kernel and working controller/picture path available.

## Recovering a black TV picture

A Steam restart during an experimental PCON boot restored the saved per-app VRR preference at 4K144 HDR and caused a black TV picture. Disabling VRR in the running Gamescope session restored the picture, confirmed by the owner:

```sh
DISPLAY=:0 xprop -root -f GAMESCOPE_VRR_ENABLED 32c -set GAMESCOPE_VRR_ENABLED 0
```

Run this as the user owning the Gaming Mode session; `:0` is the Gamescope X display used in this test. The active CRTC then reported `VRR_ENABLED=0`, while 3840×2160 at 144 Hz with HDR remained active. This is temporary signal recovery: Steam can restore its saved VRR preference again.

For persistent recovery, exit the opt-in PCON experiment and boot the accepted `7.2.9-onex3-vrr-test` default, preserving its internal-panel VRR support. Steam's VRR preference is per performance profile rather than per monitor. The current Gamescope Lua display-profile API has no per-output VRR capability override; adding an unsupported Lua setting does not protect the TV.

After returning to the accepted kernel, the TV connector reported no VRR capability and its active CRTC kept VRR off, while the built-in panel retained VRR capability. The output remained 4K144 with HDR and Decky loaded normally.

## Build and host tests

Read [manual build prerequisites and recipes](recipes/README.md) and [v3 build order](freesync-gmp/recipes/README.md). These require a reconstructed/copied accepted baseline; they do not contain a complete kernel tree or device firmware. Package revisions 1–3 historically share `7.2.9-onex3-pcon-vrr-test`, so record the package version and source identity when testing.

```sh
sh fixes/external-display-vrr/tests/run-tests.sh
sh fixes/external-display-vrr/freesync-gmp/tests/run-tests.sh
```

The suites extract exact function-only fixtures, with original notices, from the saved candidates. The AS suite covers capability/range/packet behavior and baseline pack/unpack comparisons; v3 compares every valid 1–255 Hz packet range with AMD's preserved reference implementation. Their historical totals are 9,598 and 98,002 sanitizer checks. These tests do not validate actual packet transmission, atomic ordering, converter acceptance or a physical picture. [Diagnostic clients](kms-test/README.md) are manual Linux-only tools and must not be run automatically.

## Upstream and licensing

The VTotal change is upstream [f26a8df8](https://github.com/torvalds/linux/commit/f26a8df8dff9d6e675649b76e03553f43395ed9d). Intel's [PCON/AS-v1 discussion](https://www.spinics.net/lists/intel-gfx/msg385985.html) and AMD's existing packet implementation motivate the experiment. The generic packet path should be reviewed separately from the local descriptor override; a reusable upstream quirk still needs conformance and regression evidence. No converter firmware or undocumented converter protocol is supplied.

Kernel patches retain the source files' original licensing; exact Intel/AMD function fixtures retain their notices, including [AMD-LICENSE.txt](freesync-gmp/tests/AMD-LICENSE.txt). The preserved PR13 controller source is GPL-2.0-or-later with notices in `recipes/controller-source/`. The baseline pins are documented in the [panel kernel workflow](../internal-panel-refresh/kernel/README.md) and [EDID sources](../lg-c5-edid/docs/SOURCES.md). Keep those licenses when redistributing builds.
