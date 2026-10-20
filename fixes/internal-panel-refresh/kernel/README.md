# Manual accepted display-kernel build

The accepted `7.2.9-onex3-vrr-test` combines the LG EDID recovery candidate, upstream Intel DSB fixes `f7140c7c` and `4a68c751`, and the upstream DC-balance gate `c034e8a4` defaulting off. It also preserves the signed PR13 OXP controller override plus UHID/UINPUT and supporting HID transports. The original owner accepted controls/motion and verified this kernel with the zero-lead Gamescope runtime after a normal reboot.

These are **manual research build/package helpers**, not a fresh distribution installer. They require Linux with LLVM 19 (`ARCH=x86_64 LLVM=-19`), pahole, normal kernel development dependencies, Python 3, kmod, zstd and GNU tools. Native x86-64 or ARM64-to-x86-64 Linux builds are supported by the Kbuild flags. No named container, saved volume or fixed `/input` path is needed.

## Prepare the baseline

Obtain the [exact CachyOS sources/distribution inputs](../../lg-c5-edid/docs/SOURCES.md), apply their matching recipe patches, then the EDID retry. Copy the final `lg-c5-edid/kernel/configs/test.config` to `.config`. Run `make ARCH=x86_64 LLVM=-19 olddefconfig`. The initial tree must match that EDID-test configuration and the pinned original DSB source; the helper rejects unexpected inputs. The full source tarball is deliberately not duplicated in this repository.

Keep a copy of the prepared tree. Set `tree` to its absolute path, `repo` to this checkout and `output` to a **new** absolute directory in your Linux workspace. Set `packages` to an output package directory. A different configuration/source version needs a reviewed port, not removal of the hash checks.

```sh
recipe="$repo/fixes/internal-panel-refresh/kernel"
bash "$recipe/build-display-kernel.sh" "$tree" "$output"
bash "$recipe/build-controller-module.sh" "$tree" "$output/controller-module"
bash "$recipe/package-display-kernel.sh" "$tree" "$output" "$output-stage" "$packages"
python3 "$recipe/validate-display-kernel.py" "$output-stage" "$output-validation.json"
```

The display helper applies the two DSB corrections, enables virtual-input transports, builds the matching release and records source/config/patch provenance. The controller helper rebuilds and signs the exact sibling `fixes/oxp3-controller/kernel/` source against that completed release. Packaging includes matching modules, an `updates/dkms/hid-oxp` override selected by module indexes, image/config/System.map and source/patch/license documentation; cross-host tools, headers and private keys are excluded. It never installs on the OXP3.

The result is the intermediate `linux-onex3-display-test 7.2.9-3`. From a **copy of that completed tree**, build the accepted DC-balance candidate with [vrr-candidate](vrr-candidate/README.md). Do not restore the intermediate tree's source/config before copying it for that next step. `restore-build-source.sh` is optional recovery for the two files changed by the first helper; it does not rewind compiled objects.

## Install and recover manually

Inspect the package and run the payload validator before using `sudo pacman -U /path/to/package.pkg.tar.zst` on the destination. Keep the distribution kernel installed. Native hooks must generate that machine's initramfs and a **separate** boot entry with its own matching kernel/modules; preserve the target's root/storage/encryption arguments. Inspect the generated image/entry and verify the controller override, UHID/UINPUT and InputPlumber before making this a normal boot choice.

Select the candidate from the existing boot menu for the first test; leave the working default available. A failed picture or controller test requires recovery through the retained entry. Boot another kernel before removing a candidate package. No helper writes EFI, selects a boot default, reboots, or enables external PCON VRR. [Userspace runtime selection](../permanent/README.md) is independent.

The package validators enforce the historical exact configuration, 281-module payload, signed x86-64 ELF/vermagic, display BTF and input transports. Those checks are intentionally specific to this pinned build and cannot establish compatibility on another OXP3 or current distribution kernel. Prefer current distribution packages containing the upstream corrections where available.
