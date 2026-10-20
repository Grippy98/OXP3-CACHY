# Applicability and implementation are separate

A reported symptom is a useful starting point. It does not establish the same cause on another firmware, SSD, controller stack or distribution. The review separately asks whether a change is needed and whether its implementation preserves state and has a reliable rollback.

The main implementation concerns are user-writable root payloads, destructive revert behavior, a force flag that bypasses unrelated guards, GRUB assumptions on a Limine installation, untracked firmware copies, unbounded TDP synchronization and broad ACPI/sensor overrides. The volume proxy does not resolve a missing physical key release, and generic target/filter changes need independent input tests.

[The detailed review](third-party.md) links each finding to pinned source. Source inferences are not represented as hardware reproductions. Controller, bootloader, TDP, display and power work in this collection is kept independent, with its own applicability checks and rollback. Device snapshots and binary-inspection dumps are excluded.
