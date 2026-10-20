# Why the TV output disappeared

An ALSA HDMI device and valid display audio data do not guarantee an active PipeWire sink. An analog-only card profile can hide HDMI output even with the TV connected. Selecting an available HDMI profile creates that sink asynchronously; selecting a default before it exists races profile activation.

The helper queries pactl's JSON card/profile state, refuses ambiguous outputs, changes one card profile, waits for its HDMI sink and selects that default. It preserves the first baseline on repeated application and saves new app routes before an optional move. A failed install attempts to restore the original preferences. It does not change volume, mute, firmware, EDID or audio-server configuration.

WirePlumber's [profile policy](https://gitlab.freedesktop.org/pipewire/wireplumber/-/blob/0.5.18/src/scripts/device/state-profile.lua) and [default-target persistence](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/settings.html#node-restore-default-targets) handle reconnect persistence. No unconditional service restart or forced HDMI preference is appropriate when the TV is absent. Prefer an upstream session-policy correction if the wrong profile is repeatedly selected on a clean installation.
