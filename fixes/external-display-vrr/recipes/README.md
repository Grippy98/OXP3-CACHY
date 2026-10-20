# Manual experimental kernel build

These are Linux research build/package helpers, not an installer. Start from a **copy** of the completed accepted `7.2.9-onex3-vrr-test` source/config/build tree from [the panel workflow](../../internal-panel-refresh/kernel/README.md). Its separate build-output directory must contain the baseline patches and generated `build-provenance.txt`. A full source/cache is not included here; reconstruct it first from the pinned inputs. Exact baseline hash checks intentionally reject unrelated/newer kernels and already patched trees.

Requires Linux, LLVM 19 (`ARCH=x86_64 LLVM=-19`), pahole, normal kernel development dependencies, Python 3, kmod, zstd and GNU tools. Paths are arguments and may point anywhere in your workspace; no saved container or `/input` mount is assumed. Preserve the accepted tree/package and use new output/staging directories.

Set `repo`, `tree`, `baseline`, `output` and `packages` to absolute paths. This earlier AS-v1 helper applies the experimental PCON patch followed by the upstream VTotal correction. Its physical tests failed; the limited positive SDR result requires the separate v3 prototype.

```sh
experiment="$repo/fixes/external-display-vrr"
recipe="$experiment/recipes"
bash "$recipe/build-pcon-kernel.sh" "$tree" "$output" \
  "$experiment/intel-pcon-vrr-experimental.patch" "$baseline" \
  "$experiment/intel-vrr-mode-vtotal-f26a8df.patch"
bash "$recipe/build-controller-module.sh" "$tree" "$output/controller-module"
bash "$recipe/package-pcon-kernel.sh" "$tree" "$output" "$output-stage" "$packages"
python3 "$recipe/validate-pcon-kernel.py" "$output-stage" "$output-validation.json" "$output"
```

The recipe retains baseline EDID/DSB/DC-balance patches and input transports, rebuilds/signs the pinned controller override, records exact build inputs, and packages a separately named release. Payload checks cover the historical 281-module signed x86-64 payload, vermagic/BTF/input transports, selected controller path, compiled parameter metadata and absence of headers/host tools/private keys. Both experimental controls remain off by default.

The output package is `linux-onex3-pcon-vrr-test` `7.2.9-2` with release `7.2.9-onex3-pcon-vrr-test`; historical revisions share that release string. Record package version/source identity, not just `uname`. Compilation or correct packet readback does not establish physical VRR. Installation, destination initramfs/boot-entry review and explicit one-time activation are manual; keep the accepted default and known-good controller/picture path. Never enable the experiment through a default install or infer HDR/4K success from the 1080p80 result.
