# Building for a custom kernel

The same pinned driver was successfully cross-built for the experimental EDID
kernel during the original OXP3 test. The public installer intentionally targets
CachyOS kernels with installed matching headers; it does not reuse that binary.

For a custom kernel, retain its configured and prepared full build tree and use
an external module directory containing this bundle's `hid-oxp.c`, `hid-ids.h`
and `Makefile`. In an environment with the kernel's compatible Clang/LLD tools:

```sh
make -C /path/to/prepared-kernel ARCH=x86_64 LLVM=-19 \
    M=/absolute/path/to/external-module W=1 modules
```

Check the resulting module's `vermagic` against the exact custom release and
its signing policy. Install an override under that release's `updates/` directory,
retain its stock module, run `depmod -a KERNEL_RELEASE`, and regenerate that
kernel's initramfs. Building against unconfigured sources or stock headers for a
different kernel does not establish ABI compatibility. Cross-building this file
alone does not build or install the EDID fix.
