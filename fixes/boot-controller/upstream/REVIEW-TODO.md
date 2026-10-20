# Human review tasks before submission

- [ ] Choose the intended upstream branch and reread its
  [AGENTS.md](https://github.com/Limine-Bootloader/Limine/blob/v12.x/AGENTS.md) and
  [CONTRIBUTING.md](https://github.com/Limine-Bootloader/Limine/blob/v12.x/CONTRIBUTING.md).
  The preserved tested tag and observed branch have different sign-off text.
  Do not assume either snapshot is the policy at submission time.
- [ ] Review and understand every changed file. Confirm the report decoder and
  owned USB ABI declarations against the UEFI specification. Decide whether a
  separately maintained PicoEFI declaration is preferable, without editing
  fetched dependency files in the Limine submission.
- [ ] Discuss whether maintainers want the generic `gamepad` option name with a
  narrow Xbox signature, and how future device signatures should be represented.
  Expand support only with descriptor/report evidence and tests.
- [ ] Review EFI ownership arguments, callback TPL, shutdown ordering, menu rewind,
  and all image handoff paths. Confirm the intentional refusal to boot after a
  failed cancellation; assess whether upstream wants another failure policy.
- [ ] Review neutral-input arming, dead zone/hysteresis, queue overflow behaviour,
  repeat timing, and simultaneous button handling. Keep horizontal input unable
  to accidentally boot a leaf entry.
- [ ] Review keyboard, mouse, serial, quiet-menu, entry-editor, and timeout
  integration. Check disabled input and `timeout: 0` behaviour as well as the
  normal five-second menu.
- [ ] Confirm code style, including the project's preference against unnecessary
  typedefs and terse comments. Any style changes create a new patch identity;
  preserve this tested copy and retest the changed revision.
- [ ] Recheck application against current upstream, then build the chosen revision
  and run the host and UEFI fixture tests on that revision. A clean patch check
  is insufficient evidence of build/runtime compatibility.
- [ ] Determine the appropriate build matrix. Only x86-64 UEFI was built and
  physically tested; BIOS stubs and other UEFI architectures need review/build
  coverage before claiming broader compatibility.
- [ ] Add or adapt tests to the repository's accepted layout. The local suites and
  VM fixture are outside the preserved bootloader patch. Keep installer tests
  separate from upstream driver tests.
- [ ] Repeat a physical test of the proposed submission build with a retained
  stock boot entry. Test held buttons at startup, idle automatic boot, editor
  return, repeated entry/rewind, normal Linux boot, and EFI chainload. Where
  possible, also test disconnect and transfer-error recovery. Only one physical
  successful boot is recorded so far.
- [ ] Attach the tested BIOS/firmware version and USB device/interface/endpoint
  descriptors to the hardware report. Include the details needed to reproduce
  enumeration without adding private login credentials or device identifiers.
- [ ] Keep firmware/USB/architecture limits explicit. Automatic reconnect and
  Secure Boot deployment are outside the tested behaviour.
- [ ] Provide the actual human author identity and any certification required by
  the chosen target. The bundle does not assert a DCO sign-off or authorship.
  Identify the exact assisting tool/model for the required `Assisted-by` trailer;
  do not invent or abbreviate an unknown model identifier.
- [ ] If preparing commits later, reread commit conventions immediately before
  each message. Use one logical change per commit, the required area/imperative
  subject, and normally no body. Put extended reasoning/test scope in the review
  description instead. Do not treat this draft as authorisation to submit.
- [ ] Plan maintenance for the installed custom image. It remains pinned to the
  verified build until a deliberate rebuild and test replaces it. Native CachyOS
  package upgrades currently update stock fallback, rather than this custom EFI.
