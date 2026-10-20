# Upstream direction

The local remote makes Intel RAPL available through Valve's existing API without rebuilding SteamOS Manager. A native upstream implementation belongs in [SteamOS Manager's power managers](https://gitlab.steamos.cloud/holo/steamos-manager/-/blob/v26.4.1/steamos-manager/src/power.rs), with ONEXPLAYER policy kept separate.

Preserve named-domain/constraint discovery, both MSR and MMIO controls, verified transactions, rollback on partial writes, and fake-sysfs tests. Do not derive policy from nominal `max_power_uw`, assume constraint indices, or grant the session user writable sysfs controls. Keep time windows, firmware profiles and EC behavior unchanged.

The local range is 8–40 W; [ONEXPLAYER's global specification](https://onexplayerstore.com/products/onexplayer-3-next-gen-3-in-1-ai-gaming-and-productivity-handheld) advertises 8–35 W and the [Japanese specification](https://www.onexplayer.online/onexplayer-3) offers optional 40 W. Document that extended endpoint for maintainer review. The [remote API](https://gitlab.steamos.cloud/holo/steamos-manager/-/blob/v26.4.1/data/interfaces/com.steampowered.SteamOSManager1.xml) has no enable flag or restore operation, so firmware-baseline restoration needs an explicit policy decision.

Telemetry belongs in MangoHud; read-permission policy belongs in distribution packaging/udev. Review current upstream code and contribution requirements before submitting either change.
