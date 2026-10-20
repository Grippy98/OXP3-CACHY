# LG C5 EDID recovery

See [WRITEUP.md](WRITEUP.md) for the technical explanation and upstream scope.

The TV could return as a generic 1024×768 display with HDR unavailable after a power cycle. On the tested Intel ONEXPLAYER 3 and JSAUX dock, the display converter retained a nonzero EDID segment pointer: a later base-block read returned an extension block instead of the base header.

The [kernel candidate](kernel/edid-segment-reset-retry.patch) retries only a successful full base-block read whose header has no matching bytes, explicitly writing segment zero. Valid reads, repairable headers, short probes and the existing five-attempt budget keep their current behavior. This is a local, unmerged candidate; it is not a general claim about all LG TVs or docks.

The separate [saved-EDID workaround](workaround/manage-edid.py) uses **your own known-good LG TV EDID** on one named output. No captured EDID, serial number, firmware binary or device boot configuration is distributed.

## Install the workaround

Requires CachyOS/Deckify with Limine entry tools, mkinitcpio and Python 3. First restore normal TV detection with its 3840×2160 modes available; do not capture the generic/fallback state.

From the repository root:

```sh
./install.sh check display-edid
./install.sh install display-edid --connector DP-1 --capture
# Or supply your own complete known-good file:
./install.sh install display-edid --connector DP-1 --edid /path/to/my-lg-tv.edid
./install.sh rollback display-edid
```

The dispatcher obtains administrator access for installation/rollback. For direct use, run `sudo bash fixes/lg-c5-edid/install.sh ...` and `sudo bash fixes/lg-c5-edid/rollback.sh`. The connector name is explicit; inspect `/sys/class/drm/` on the destination machine.

Installation verifies the EDID header, exact extension count, every block checksum, LG TV identity and a CTA extension. Live capture also requires a connected output with a 3840×2160 mode and rejects an existing firmware override. It saves the EDID under `/usr/lib/firmware/edid/`, writes dedicated Limine/mkinitcpio snippets, backs up replaced files under `/var/lib/oxp3-cachy/display-edid/`, and rebuilds startup files. It does not reboot or change the boot default. The new command-line setting takes effect on the next boot.

Rollback checks that managed files have not been edited, restores their previous contents and rebuilds the initramfs/startup files. Disable this fixed EDID before connecting a different monitor to that connector. Other EDID overrides must be resolved first; this adapter deliberately refuses to merge them.

## Tested status and limits

The kernel candidate was built and booted as `7.2.9-onex3-edid-test`. Three forced stale-segment reprobes recovered the correct EDID. A subsequent TV power cycle retained 4K144/HDR, but did not itself trigger a new I²C read. This demonstrates the narrow recovery path, not universal dock compatibility.

The host transport suite covers 21 cases, including stale pointers, valid/repairable headers, legacy sinks, NAKs, short reads and retry-budget exhaustion, with address/undefined-behavior sanitizers. It uses synthetic blocks and actual extracted kernel functions:

```sh
python3 fixes/lg-c5-edid/kernel/patch-tests/make_and_test.py
python3 fixes/lg-c5-edid/tests/test_manager.py
```

The portable workaround adapter is new packaging code; no new device installation is claimed. Read [build/prerequisites](docs/BUILD.md), [manual kernel installation](docs/INSTALL.md) and [source pins/licensing](docs/SOURCES.md).

## Upstream path

Submit the transport reproducer and bounded retry separately to DRM maintainers. Broader sink testing is still required: some devices reject segment-zero writes, and the narrow header trigger intentionally misses partially matching invalid data. A bridge-specific quirk or a different recovery layer may be preferred. The host test does not model DP AUX timing, concurrent DDC users, HPD or suspend/resume.
