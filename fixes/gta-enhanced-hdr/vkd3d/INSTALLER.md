# Per-game vkd3d Core installer

This helper installs **only the official vkd3d-proton 3.1 x64 `d3d12core.dll`** beside `GTA5_Enhanced.exe`. It leaves the D3D12 loader, prefix, Proton, DLL overrides, INI files and Steam settings alone. The runtime result and current HDR/FG limits belong to the surrounding HDR documentation; a successful install/check does not establish game compatibility or prove which DLL the game loaded.

Run on Linux as the game-owning user, with GTA fully closed. Python 3 and either `bsdtar` (libarchive), or GNU tar plus `zstd`, are required. The helper installs no packages and executes no downloaded installer scripts or DLLs.

## Use

From this folder:

```sh
python3 install-vkd3d.py check
python3 install-vkd3d.py install
python3 install-vkd3d.py rollback
```

The default searches the usual `~/.local/share/Steam` and `~/.steam/steam` GTA installation, resolves duplicate symlink aliases, and requires `GTA5_Enhanced.exe`. Use an explicit folder for another Steam library:

```sh
python3 install-vkd3d.py install --game-dir "/path/to/Grand Theft Auto V Enhanced"
```

Installation downloads and verifies the pinned official archive. For a previously downloaded copy:

```sh
python3 install-vkd3d.py install --game-dir "/path/to/Grand Theft Auto V Enhanced" \
  --archive "/path/to/vkd3d-proton-3.1.tar.zst"
```

Only the fixed member `vkd3d-proton-3.1/x64/d3d12core.dll` is read from the archive; its bytes are checked again before installation. The other DLL and `setup_vkd3d_proton.sh` are not extracted or executed. Downloads are bounded to 16 MiB; existing files/backups are bounded to 128 MiB.

| Pinned input | Value |
| --- | --- |
| [Official release](https://github.com/HansKristian-Work/vkd3d-proton/releases/tag/v3.1) | `v3.1` |
| Release source | `4522cc1a8b1347f1ab1b0f7b14a23ed9444d95d1` |
| Included upstream fence fix | `49a1e2c7098f4646374458b9a8fbc7c0d0b5ff3d` |
| Archive SHA256 | `b85ea8219b71093a3924913dd7aae6172333dc0c069983ed510816d67f02120b` |
| x64 Core SHA256 | `0dfd690a39ef8361ca3b64e9fd8e945b27d2c568dac5dc0dce1a45abf65914cc` |

Keep the release's LGPL/upstream notices with private downloaded files. This folder contains no release binaries or game files; the helper is separate collection glue, not upstream's prefix installer.

## Launch setup stays separate

Follow the surrounding HDR guide for the scoped `d3d12core=n,b` preference, retaining existing Wine overrides and the OptiScaler DXGI entry. This helper does not add or remove that preference. Keep the original **system32 `d3d12.dll` loader** used by the inspected ReShade configuration; reconcile an earlier app-directory loader diagnostic manually from its own backup.

After launching, verify the actual loaded paths: original system32 D3D12 loader and game-directory Core. Check ReShade/RenoDX initialization and actual HDR/SR separately. Updating a DLL or reaching a menu alone does not prove those features are active. Remove only this fix's scoped Core override when rolling back; the helper does not edit launch settings for you.

## Backup and rollback behavior

The helper records the resolved game path and exact filename case in `.oxp3-vkd3d-core/state.json`. It records an absent original as absent, preserves a symlink's target verbatim, or stores a regular-file backup with its hash, permission mode and modification time. Symlink targets are not modified. File publication uses a same-directory atomic replacement; an advisory lock prevents concurrent helper mutations.

Repeated installation verifies the installed hash and original backup, then keeps that backup. Rollback restores the recorded absent/file/symlink state only while the current Core matches the installed release. If the exact original is already restored after an interrupted rollback, the helper finalizes metadata without overwriting it. Backups remain after rollback and are reused for a later install while the original state still matches.

The helper refuses conflicting filename case variants, symlinked state/backup paths, mismatched game-path records, corrupt backups and unknown Core replacements. If a game update or another mod changes the Core, inspect those changes instead of forcing a rollback. It also refuses check/install/rollback while a GTA process is detected, and rechecks before mutating files. Keep the game closed until the command completes.

`check` writes no files and never downloads. Exit codes: `0` for an active recorded installation or successful install/rollback; `1` for an inactive check; `2` for an error or refusal. A missing installation is not proof that the system/prefix Core lacks the upstream fix.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
```

The 23 tests cover backup/rollback of absent files, existing files and relative/dangling links; filename case collisions; scope; corrupt/foreign state; unknown replacements; process detection; archive hashes/member selection; bounded download; literal subprocess arguments; lock contention and interrupted publication/rollback. All 23 tests passed on the CachyOS device in a temporary folder. The staging Mac passed 22 and skipped its case-collision fixture on its case-insensitive filesystem. The real pinned archive and selected Core hash also passed extraction on the Mac and CachyOS. A temporary CachyOS CLI install/check/rollback restored the exact pre-existing fixture. The existing device Core was then brought under installer management with its original absence verified from the earlier backup record; its binary hash did not change, and the managed check passed. These installer tests execute no DLL or game and do not qualify HDR or frame generation.
