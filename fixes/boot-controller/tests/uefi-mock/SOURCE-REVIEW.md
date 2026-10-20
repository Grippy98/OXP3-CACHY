# Independent controller source review

Reviewed the first complete native controller implementation against the exact
Limine v12.9.0 source, following the earlier design review. No production source
was edited by this reviewer.

No blocking issue was found in the reviewed normal path:

- USB IO layout and packed descriptor offsets match the independent runtime
  fixture. The driver validates VID/PID, interface, and interrupt endpoint.
- BY_DRIVER ownership uses valid agent/controller handles, avoids exclusive
  access, and skips an occupied interface.
- Fixed static context is excluded from menu data rewind. Callback/main-loop
  state is protected at TPL_NOTIFY; receive pointers are not retained.
- Startup requires neutral input, confirmation is edge-triggered, and directions
  repeat independently of USB report arrival. A transfer error clears state.
- The input event array accommodates all 16 pointer events plus controller,
  keyboard, and timeout. It rebuilds indexes after controller deinitialisation
  and preserves the existing timeout across idle controller timer ticks.
- Common boot, memory release, EBS, firmware reset, editor, and menu rewind paths
  stop controller input. Panic recovery can reinitialise controller input.
- Failed async cancellation blocks handoff rather than freeing live callback
  code. Successful cancellation precedes timer closure and protocol release.

Document these limits: errors from CloseProtocol/CloseEvent are not separately
reported; automatic controller reconnection within the current input wait is
not implemented after a transfer failure. Existing keyboard/timeout input stays
available. Hardware USB enumeration and cancellation behaviour still need the
separate experimental firmware test.

The private QEMU runtime fixture independently confirmed actual EFI protocol
discovery/claim, callback invocation at TPL_NOTIFY, Down selecting the second
entry, Up selecting the first entry, A choosing its actual EFI LoadOptions,
and exactly one async cancellation before EFI chainload. Three screenshots
were inspected to verify both intermediate selections and target success.
The disabled negative control submitted no USB input and did not boot.
The idle-report countdown scene supplies neutral reports every 20 ms; see its
result JSON for the separate autoboot verification and copied EFI hash.

The final tree scene also passed on EFI SHA256
`ebbb41d6f9a1e97322928327869e80ee3f0523714150ab04bf3092e80c7e19b7`.
Three inspected screenshots show B selecting/collapsing an immediate nested
parent under an expanded outer parent, Right re-expanding the selected nested
parent, and Down selecting its expected child. A booted that child's actual
EFI LoadOptions and the target verified cancellation before chainload.
Evidence is in `results/tree-back-expand/`. These results still do not claim
real USB firmware behaviour or a runtime ExitBootServices test.
