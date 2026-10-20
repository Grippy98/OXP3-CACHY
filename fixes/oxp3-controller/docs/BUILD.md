# Build and package the controller driver

Use [the pinned sources](../kernel/SOURCES.md). Build against the exact headers
for the kernel that will load the module:

```sh
cd fixes/oxp3-controller/kernel
make -C "/usr/lib/modules/$(uname -r)/build" M="$PWD" W=1 modules
```

The source was tested with CachyOS 7.2.9 headers. Compatibility with another
kernel must be established by building against its own configuration and symbol
versions. A module from one kernel release must not be copied to another.

The source-only Arch package can be made on Linux or macOS with Bash, Python 3,
`install`, `du`, `awk` and `sha256sum` or `shasum`:

```sh
bash fixes/oxp3-controller/kernel/package-controller-fix.sh /tmp/oxp3-packages
```

With no output argument it uses `kernel/build/`. The package contains sources,
DKMS configuration, ABI documentation and licenses; it contains no module binary.
Python's GNU tar writer normalizes ownership and avoids macOS PAX attributes.
Timestamps and build date vary, so the archive is not byte-reproducible.

The [root installer](../README.md) installs/builds directly through DKMS and does
not require making this package. If installing the source package manually, use
`pacman -U`, then `dkms autoinstall -k "$(uname -r)"`, `depmod`, and the CachyOS
initramfs generator. The package needs DKMS hooks and matching headers.
