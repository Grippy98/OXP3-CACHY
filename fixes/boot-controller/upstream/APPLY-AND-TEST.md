# Apply and evaluate the preserved patch

Work in a separate clean full Limine source tree. The parent bundle's `limine/`
directory contains changed sources and supporting headers for local review/tests;
it is not a full upstream build tree. Keep the installed image and the preserved
patch unchanged while evaluating a revision for submission.

## Read-only application check

The script verifies the preserved patch hash, then checks application and
whitespace without changing the source tree. It accepts a clean Git checkout or
an extracted full source archive.

```sh
review_tree=/path/to/full/clean/Limine
bash check-patch.sh "$review_tree"
```

Run this from the `upstream/` directory. The exact tested base is
`34fe53c3d27d229ea25c28fc3e04db362543715b` (`v12.9.0`). The historical newer branch
snapshot is recorded in `README.md`. If using Git, verify the
checkout's identity and clean status before application:

```sh
git -C "$review_tree" rev-parse HEAD
git -C "$review_tree" status --short
```

Review any output before proceeding. The check script cannot establish that
unrelated existing source changes are harmless.

## Apply after reviewing the patch

The following command changes only the selected review tree. It does not commit,
stage, install, or submit anything:

```sh
git -C "$review_tree" apply "$PWD/limine-gamepad-tested-v12.9.0.patch"
```

For a Git checkout, inspect tracked and newly created files; `git diff` alone
does not show untracked new files. Read the five new driver/state/USB headers and
sources directly, then inspect the changed input, menu, cleanup, and config files.

```sh
git -C "$review_tree" status --short
git -C "$review_tree" diff --check
git -C "$review_tree" diff --stat
```

Do not use `--3way`, reject-file application, or silently resolve a conflict while
calling the result the preserved tested patch. Save a separate candidate patch
and record its new hash after any edit/rebase.

## Reproduce the tested build and existing tests

From this folder, the parent recipe builds the pinned release plus the original
patch in a disposable source directory. Supply an output directory so generated
files remain outside the review documents:

```sh
bash ../build.sh /path/to/generated/limine-controller-build
bash ../tests/run-state-tests.sh
bash ../tests/run-firmware-tests.sh
bash ../tests/run-wait-tests.sh
```

The recipe uses Docker/Clang 19 and verifies the release archive checksum.
The recorded tested build used an existing Debian container. The equivalent fresh
Docker recipe has not independently been executed. A rebuild may have a different
binary hash; record its toolchain and hash rather than assuming byte identity.

For sanitizer checks:

```sh
CC='clang -fsanitize=address,undefined -fno-omit-frame-pointer' bash ../tests/run-state-tests.sh
CC='clang -fsanitize=address,undefined -fno-omit-frame-pointer' bash ../tests/run-firmware-tests.sh
CC='clang -fsanitize=address,undefined -fno-omit-frame-pointer' bash ../tests/run-wait-tests.sh
```

These existing scripts test the preserved parent-folder source. To test a changed
candidate tree, adapt a separate copy of the test harness to point at that tree;
do not overwrite the validated local source and then reuse its old provenance.
Use the chosen full tree's documented bootstrap/configure/build procedure for
its new revision rather than the pinned release recipe.

The [independent UEFI fixture](../tests/uefi-mock/README.md) documents QEMU/OVMF
navigation, disabled-input, idle-autoboot, and nested-directory scenes. Its build
script requires an existing Docker container with Clang/LLD 19; select that
container with `--container`. Its runner accepts the candidate EFI with `--limine`.
Keep generated VM state outside review material, inspect intermediate highlighted
entries, and record the exact candidate hash with results.

## Physical verification and submission preparation

Use the parent experimental install and one-shot test workflow only after building
and reviewing the candidate. Those scripts assume the reviewed CachyOS layout
and discover the stock firmware entry dynamically; they are not upstream installers.
Keep stock boot files and the tested controller image recoverable. A later
physical test needs the candidate's own evidence record, rather than overwriting
the completed v12.9.0 validation.

Finish [the human review tasks](REVIEW-TODO.md) before preparing commits or an
actual review request. This preparation folder does not create either.
