# Installation and rollback

## Requirements

Use the Intel ONEXPLAYER 3 with CachyOS/Arch, Python 3 and a normal logged-in Gaming Mode/Desktop user. Keep the distribution's packages coherent; the installer does not perform a system upgrade. Clone the whole repository so sibling sources and licenses remain available.

Start `./install.sh` in a terminal. Choose numbers separated by spaces, then **check**, **install**, **rollback** or **docs**. Each selected fix runs separately; failed checks or installation are reported per fix. There is no unattended install-all action.

The CLI is suitable for repeatable individual actions:

```sh
./install.sh check tdp
./install.sh install tdp
./install.sh install metrics
./install.sh install tv-audio
./install.sh rollback tv-audio
```

`--session-user NAME` (or `--session-user=NAME`) selects a session user when needed. Otherwise the original non-root user is used. User fixes run in that user's session, even if the dispatcher was launched with sudo. Checks do not install packages or change settings.

## Fix-specific inputs

| ID | Additional input | Rollback |
| --- | --- | --- |
| `controllers` | Optional kernel release; matching headers and build packages required | Pass the backup directory printed by its installer |
| `boot-controller` | Path to a locally built `BOOTX64.EFI`, optional expected SHA256 | Default restores the stock boot order; `--remove` separately removes staged EFI files |
| `power-button` | Active Gaming Mode user | Keeps preexisting packages and restores recorded daemon activity |
| `tdp` | Session user, detected automatically in a normal shell | Removes managed activation/drop-ins and restores original limits |
| `metrics` | Exact supported RAPL/PMT sensors | Restores managed permissions/service files |
| `tv-audio` | `--card NAME`, `--profile NAME` when ambiguous; optional `--move-streams` | Restores saved profile/default; refuses to overwrite later preferences unless `--force` |
| `display-edid` | `--connector DP-1 --capture` or `--connector DP-1 --edid /path/to/edid.bin` | Restores managed files and rebuilds initramfs |
| `panel-refresh` | Normal user | Restores the prior Lua profile; this adapter does not install the kernel/runtime |

For example, with the LG TV on and currently reporting its complete modes:

```sh
./install.sh install display-edid --connector DP-1 --capture
```

Never capture an already truncated or incorrect EDID. An override is specific to the connected display and connector; consult its README before reuse.

## Bootloader controller support

Build from [the pinned Limine source](../fixes/boot-controller/README.md), then select the boot-controller menu item or run:

```sh
./install.sh install boot-controller /path/to/BOOTX64.EFI
```

The adapter stages a separate EFI application and prints one-time testing steps. It does not select the new loader as the default or reboot. After a successful controller test, follow the separate promotion instructions in that folder. Keep the stock loader available.

## Builds and experiments

MangoHud telemetry, the complete accepted panel kernel/runtime, EDID kernel recovery and external VRR require source builds or explicit prebuilt inputs. The menu links their instructions rather than silently building or replacing the running graphics stack. In particular, external VRR is not a working 4K/HDR fix and is excluded from automatic installation.

## Backups

Each adapter prints its backup path. System backups are root-owned under `/var/lib/`; user preferences use the user's XDG state/config directories. Keep them until rollback is no longer needed. No backup or captured EDID belongs in Git.

Read the individual rollback instructions before removing a kernel, loader or controller driver. This collection does not erase a recovery boot entry or reboot automatically. Rollback may refuse when files changed independently after installation; resolve that conflict instead of deleting the backups.
