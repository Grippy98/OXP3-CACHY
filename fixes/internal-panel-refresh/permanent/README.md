# Manual accepted-runtime selection

The original device accepted the internal VRR setup on `7.2.9-onex3-vrr-test`, with the guarded Gamescope executable, HDR/VRR enabled, fixed wake lead **0** and tracing **0**. That full combination was persisted and verified by a normal reboot. The public `panel-refresh` adapter installs only the Lua profile; it does not reproduce these kernel/runtime steps automatically.

Build the [kernel](../kernel/README.md) and [accepted Gamescope runtime](../gamescope/README.md) first. Keep the distribution kernel, Gamescope executable and boot entry available. The commands below select the isolated userspace runtime on a Deckify installation whose session resolves `gamescope` through PATH. Inspect `systemctl --user cat gamescope-session.service` before using the drop-in. An absolute executable path requires adapting the destination service instead.

Set `repo` to this checkout's absolute path and `work` to the completed Gamescope build. Run these as the Gaming Mode user. An existing `/opt/onex3/gamescope` must be backed up/reviewed first; the check refuses replacement.

```sh
test ! -e /opt/onex3/gamescope
sudo install -d /opt/onex3 /opt/oxp3-cachy/bin /etc/oxp3-cachy
sudo cp -a "$work/stage/opt/onex3/gamescope" /opt/onex3/gamescope
sudo chown -R root:root /opt/onex3/gamescope
sudo install -m755 "$repo/fixes/internal-panel-refresh/permanent/gamescope"   /opt/oxp3-cachy/bin/gamescope
stock_hash=$(sha256sum /usr/bin/gamescope | cut -d ' ' -f1)
candidate_hash=$(sha256sum /opt/onex3/gamescope/bin/gamescope | cut -d ' ' -f1)
printf '%s %s %s\n' "$stock_hash" "$candidate_hash" /opt/onex3/gamescope/bin/gamescope |   sudo tee /etc/oxp3-cachy/gamescope-runtime >/dev/null
sudo chmod 644 /etc/oxp3-cachy/gamescope-runtime
mkdir -p "$HOME/.config/systemd/user/gamescope-session.service.d"
test ! -e "$HOME/.config/systemd/user/gamescope-session.service.d/80-onex3-display.conf"
cp "$repo/fixes/internal-panel-refresh/permanent/80-onex3-display.conf"   "$HOME/.config/systemd/user/gamescope-session.service.d/"
systemctl --user daemon-reload
```

Close games and restart Gaming Mode through the normal UI when ready. Verify the running executable, active kernel, real output timing, HDR/VRR and controller input. The wrapper falls back to distribution Gamescope if the candidate or stock checksum changes; review/rebuild after a package update. The compiled resource/WSI prefix is `/opt/onex3/gamescope`, so do not move that runtime tree arbitrarily.

The drop-in enables HDR/VRR and explicitly sets lead/tracing to zero. It contains no fixed positive lead and enables no external PCON experiment. Kernel install/boot selection is a separate manual step; do not change the normal default until a controlled test confirms picture and controls. Prefer the retained distribution entry to recover from a failed candidate.

To roll back userspace selection, remove only `80-onex3-display.conf` from the user service drop-in directory, run `systemctl --user daemon-reload`, and restart Gaming Mode after closing games. Boot the retained distribution kernel to roll back the kernel path. Leave the isolated runtime files available until recovery is verified; they can then be removed manually. The refresh-profile adapter has its own rollback and is independent of runtime selection.
