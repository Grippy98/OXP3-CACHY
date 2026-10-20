# Steam TDP slider for Intel ONEXPLAYER 3

SteamOS Manager needs a hardware backend before it can expose a TDP slider. This local remote connects Valve's existing API to Intel RAPL and keeps package limits synchronized across both the MSR and MMIO interfaces. It discovers constraints by name, verifies every request, and rolls back partial writes.

Policy advertises 8–40 W: 8–35 W is the normal manufacturer range, with an optional 40 W endpoint. Starting changes no limits. Graceful stop restores that process's fresh baseline; the Steam checkbox has no separate restore API.

Use [installation and behavior](INSTALL.md) for prerequisites, commands, checks and rollback, and [upstream direction](UPSTREAM-PLAN.md) for the generic native-backend proposal. The installed runtime is independent of MangoHud and the permissions helper.
