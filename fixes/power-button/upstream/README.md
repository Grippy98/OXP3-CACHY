# CachyOS model-recognition proposal

The [patch](0001-chwd-recognize-onexplayer-3.patch) adds the exact OXP3 model to the handheld profile allowlist in [chwd](https://github.com/CachyOS/chwd/tree/2d963e942bbd4551698bfdd7de7b533139347c78). That makes the normal handheld dependencies, including the native power-button handler, available during device setup.

This is a pinned, unpublished proposal; it is not applied by the collection installer. The installer uses CachyOS's packaged daemon directly. Reference source and its original license files are retained under `reference/`. See [the writeup](../WRITEUP.md) for the handler/package source revisions and the distinction between missing installation and a hardware-driver defect.
