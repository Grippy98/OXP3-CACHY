# TV HDMI audio profile

The LG TV's HDMI audio was detected by ALSA/PipeWire, but the selected analog-only card profile did not create an HDMI sink. Choosing the native HDMI profile and default output restored audio; a dock reconnect was physically tested.

## Use

Run from the logged-in audio session:

```sh
./install.sh check tv-audio
./install.sh install tv-audio
```

The menu can collect a card/profile. If several are available, use the names printed by the check:

```sh
./install.sh install tv-audio --card CARD_NAME --profile PROFILE_NAME
```

`--move-streams` also routes running applications. Volume and mute are retained. The helper waits for asynchronous sink creation and writes a private baseline under `$XDG_STATE_HOME/oxp3-cachy/tv-audio/` (default `~/.local/state/`). WirePlumber saves its native preferences; no custom sound daemon or kernel patch is installed.

## Rollback

```sh
./install.sh rollback tv-audio
```

This restores the previous card profile/default output and surviving recorded app routes. Later independent preference changes cause a refusal; after inspecting the backup, `--force` explicitly restores it. Reconnect the card before rollback. Existing app stream IDs are transient, so restoration is best effort for applications still running.

The native profile repair was hardware tested. The generalized transactional helper is host-tested with a fake audio backend and has not been deployed to another device. See [WRITEUP.md](WRITEUP.md).
