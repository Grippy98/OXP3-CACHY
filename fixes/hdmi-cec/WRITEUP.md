# Native CEC on a USB-C display path

Linux's [DP CEC helper](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/display/drm_dp_cec.c) registers an adapter only when the downstream converter advertises CEC tunneling. A zero capability byte is distinct from a CEC pin that is advertised but not physically wired; software discovery alone cannot prove the wiring.

The source probe maps connected DP connectors to their AUX character devices, reads receiver/branch/CEC capability data and repeats the CEC capability read. It also reports kernel CEC configuration and existing CEC nodes. It performs no protocol writes.

No tested software-only CEC fix is available for the converters in this setup. Keep CEC transport evaluation separate from high-bandwidth video/VRR tests. A separate USB-CEC adapter can sometimes use another TV port while video bypasses it, but device addressing, TV routing and power behavior still require testing.
