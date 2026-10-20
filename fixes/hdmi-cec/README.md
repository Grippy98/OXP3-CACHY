# HDMI-CEC transport check

Neither tested USB-C display converter exposed a usable CEC transport. The kernel had DP-AUX CEC support, but both converters returned zero for the tunneling capability and Linux created no `/dev/cec*` device. This is a hardware/firmware boundary, not an installed CEC-client setting.

## Recheck your adapter

With the TV connected:

```sh
sudo python3 fixes/hdmi-cec/probe-cec.py
```

The probe only reads capability registers and prints a report. It sends no CEC commands and writes no adapter registers. The menu entry links this diagnosis; it does not install a daemon or claim to enable missing transport.

An adapter that exposes DP-AUX CEC or a separate USB-CEC transport is required before client configuration can help. CEC support cannot be inferred from HDMI version, HDR or maximum refresh rate. Wake of the handheld itself is a separate USB/firmware feature.

See [the implementation writeup](WRITEUP.md) and the [kernel CEC documentation](https://docs.kernel.org/admin-guide/media/cec.html).
