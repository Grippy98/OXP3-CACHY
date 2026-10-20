# Upstream review preparation

The controller change is a local opt-in patch, with no claimed upstream
acceptance. [The proposal](PROPOSAL.md) explains its design and limitations;
[application instructions](APPLY-AND-TEST.md) and [review tasks](REVIEW-TODO.md)
help evaluate a future submission.

The preserved `limine-gamepad-tested-v12.9.0.patch` is byte-identical to the
[parent patch](../limine-gamepad.patch). Its base and SHA256 are documented in
[the source pins](../SOURCES.md). Review source changes in a separate complete
Limine tree. `check-patch.sh CLEAN_SOURCE_DIRECTORY` checks application and
whitespace without applying changes. Historical application checks succeeded on
both the tested v12.9.0 base and `v12.x` snapshot
`e3aa138d383ca4fe061f05931b5a54497cd502f2`; the latter was not built or physically
tested. Recheck the intended revision when preparing a submission.

Limine's [contribution policy](https://github.com/Limine-Bootloader/Limine/blob/v12.x/CONTRIBUTING.md)
requires human responsibility and assistance disclosure. Reread the chosen
revision's policy before preparing commits. Original policies in the source
subset are retained unmodified. This packaging supplies no human certification,
new sign-off, or upstream submission.
