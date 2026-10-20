# Intel power controls and telemetry

The RAPL backend discovers sustained and short-term package limits by name in MSR/MMIO interfaces, applies bounded requests with verified readback and restores failed transactions or the baseline at service stop. The OXP3 policy is 8–40 W, with 40 W an optional device setting rather than an inferred generic CPU maximum. See [the README](README.md) and [upstream plan](tdp/UPSTREAM-PLAN.md).

Telemetry distinguishes package energy from graphics/uncore energy, uses the exact supported Intel PMT GT temperature schema, and labels resident shared GTT memory rather than dedicated VRAM. [The MangoHud patch and credits](telemetry/README.md) describe the source build and remaining scope.

The permissions helper grants only the required telemetry reads; it does not grant power-limit writes to desktop processes. D-Bus activation/lifecycle and file installation are transactional, root executables are root-owned, and rollback restores managed state. The menu exposes TDP and telemetry permissions separately from building/installing a replacement MangoHud package.
