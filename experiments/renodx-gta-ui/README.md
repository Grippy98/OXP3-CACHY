# GTA Enhanced RenoDX HUD build

This isolated recipe builds the exact RenoDX source commit recorded in
`source.json`, using its recursively pinned submodules, upstream Clang x64
Release preset, and only the `gtav-enhanced` target. No global upstream preset,
CMake file or submodule revision is changed. The normal CMake shader target
regenerates and embeds the final proxy pixel shader.

`tools.json` pins the official DXC, Slang and glslang release archives and SHA256
digests. The versions match the pinned RenoDX tool manifest. Clang and Windows
SDK come from the Windows runner; compiler versions are recorded in the artifact.
The artifact contains the addon, source patch, upstream license and provenance;
it does not contain SDK/tool binaries, game files or diagnostic captures.

The initial empty patch is an unmodified-source build control. It does not
implement HUD composition, install anything, or qualify the runtime. A later
HUD consumer patch must be reviewed together with its matching OptiScaler COM
packet producer before either binary is installed. Build success alone does not
establish correct colors, synchronization, HUD output or generated-frame output.

The optional bridge must compose the game UI during RenoDX's existing HDR
presentation pass, preserve the original scene conversion when absent, and use
explicit resource ownership and queue ordering. It must not expose RenoDX's
internal C++ containers across addon boundaries.

Primary sources: [pinned RenoDX source](https://github.com/clshortfuse/renodx/tree/bc0ead39917634e95c534f7e8cfb59ab82880747),
[upstream Clang workflow](https://github.com/clshortfuse/renodx/blob/bc0ead39917634e95c534f7e8cfb59ab82880747/.github/workflows/clang-x64.yml),
[shader/compiler build rules](https://github.com/clshortfuse/renodx/blob/bc0ead39917634e95c534f7e8cfb59ab82880747/CMakeLists.txt).
