# Implementation and upstream direction

Linux delivered ACPI power events, but the Gaming Mode configuration left them to a userspace handler that was absent. Valve's powerbuttond finds inputs tagged `STEAMOS_POWER_BUTTON=1` and sends Steam's short/long power commands. OXP3 needs no daemon-specific model patch.

An older `/etc/udev/hwdb.bin` can take precedence over a refreshed vendor cache during live installation. The adapter runs `systemd-hwdb update`, reloads udev and refreshes existing inputs named Power Button before starting the user unit. It does not combine the handler with another suspend-on-power logind override.

The reviewed handler is Valve v4.2, commit `9392e68883fdb0c40bc01ab39ae75c83a541e413`. Pinned licensed reference files are under `upstream/reference/powerbuttond-v4.2/`. CachyOS packaging was reviewed at [`30d23872`](https://github.com/CachyOS/CachyOS-PKGBUILDS/tree/30d23872cb8b307e162386d60fc7d9a241a955b4/handheld/steamos-powerbuttond). The proposed [chwd model allowlist patch](upstream/0001-chwd-recognize-onexplayer-3.patch) targets commit `2d963e942bbd4551698bfdd7de7b533139347c78`.

Package/service rollback is separate from upstream model recognition. The installer records ownership only after observing installation, preserves a preexisting package and its activity, and does not reuse another user's baseline.
