# InputPlumber 0.81.0 mapping review

Reviewed release source is preserved under `reference-v0.81.0/`. This review describes the pinned v0.81.0 version; revisit it when changing InputPlumber versions.

## Source filtering

[`SourceDriver::new_with_options` and `should_filter`](https://github.com/ShadowBlip/InputPlumber/blob/v0.81.0/src/input/source/mod.rs) recognize `exclude: ["*"]`, which enables filtering without inserting a normal capability into the exclusion set. With an empty exclusion set and a nonempty inclusion set, `should_filter` rejects every capability except those included. The OXP3 profile therefore accepts only Ctrl, Alt, Meta, and O from the companion keyboard. This is a whitelist, so the rest of that keyboard's keys are not forwarded by this source.

## Chord timing and matching

[`CompositeDevice::translate_capability`](https://github.com/ShadowBlip/InputPlumber/blob/v0.81.0/src/input/composite_device/mod.rs) treats version-1 source events as an inclusive set of held capabilities. It emits a target when every configured key is down; additional held keys do not prevent a match. Repeated presses of a capability already recorded as held return early. A target releases only after every key belonging to its source chord is released. Consequently, holding common Ctrl/Meta modifiers while switching between the two factory chords can overlap their targets. The individual physical button tests completed successfully; simultaneous factory-button combinations were not separately tested.

The default device profile expands `Keyboard` to Guide + North. `handle_event` schedules multiple target button events in sequence, with 80 ms spacing, and reverses their release order. The Xbox target expands `QuickAccess` to Guide + A with equivalent spacing. These implementations preserve a usable virtual chord even when a factory button's physical press is short.

## Capability-map outputs are nonrecursive

Raw source events enter `process_event`. Capabilities requiring a capability-map translation go to `translate_capability`, and the raw event returns without continuing to normal output handling. Mapped events then call `handle_event` directly, or are queued as `CompositeCommand::HandleEvent`; they do not return through `process_event` and the capability-map layer.

Version-1 mapping sources use the same [`CapabilityConfig`](https://github.com/ShadowBlip/InputPlumber/blob/v0.81.0/src/config/capability_map.rs) type as targets. A source such as `gamepad: {button: Keyboard}` is therefore supported by the Rust configuration and JSON schema. A future raw Keyboard → Guide mapping would not remap a Keyboard generated from Ctrl + Meta + O. That change was reviewed but is **not included** in the final tested configuration.

The capability-map held-input list is shared across sources. Two physical reports representing different menu capabilities could still yield distinct menu actions; nonrecursive translation is not a blanket deduplication guarantee. Here, the individual capture distinguished the companion keyboard chord from Home's vendor `0x24` report, and the tested two-entry map was retained after the owner's confirmation.

## Override loading and ownership

[`src/config/path.rs`](https://github.com/ShadowBlip/InputPlumber/blob/v0.81.0/src/config/path.rs) supports local device definitions in `/etc/inputplumber/devices.d/` and maps in `/etc/inputplumber/capability_maps.d/`. Matching local device filenames take precedence over vendor definitions. Capability maps loaded from `/etc` replace maps with the same ID. The local map ID remains `oxp9`.

InputPlumber reads the companion HID input and creates the virtual controller. The tested `hid-oxp` kernel module supplies the OXP MCU configuration and corresponding controller fixes. Replacing only the userspace configuration does not establish that the companion firmware emits both rear buttons on an unpatched kernel. Both layers were present in the successful test.
