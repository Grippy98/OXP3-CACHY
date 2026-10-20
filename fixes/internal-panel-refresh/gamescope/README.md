# Gamescope builds

The accepted executable is built by [accepted-runtime/build.sh](accepted-runtime/build.sh), from Valve Gamescope **3.16.25**, commit `17baf4abd1ab3353fb705e4d0d023f84e870f7e8`, plus the adjacent complete guarded timer/trace patch. It contains diagnostic controls and consumed-target protection; extra wake lead and tracing default to zero. The accepted VRR runtime uses those zero values. Positive fixed-refresh lead is research, not a default fix.

Use native x86-64 Linux with Git, Meson, Ninja, CMake, C/C++ compilers, pkg-config, glslangValidator, wayland-scanner and Python 3. Development packages must provide Wayland/protocols, Catch2, libdrm, Vulkan, PipeWire, libinput, libseat, AVIF, libeis, libdecor, libcap, LuaJIT and pixman. The recipe checks these before fetching pinned source/subprojects.

```sh
JOBS=4 bash fixes/internal-panel-refresh/gamescope/accepted-runtime/build.sh   "$HOME/oxp3-build/gamescope-accepted"
```

The destination must be new. The script verifies the base/patch/subproject identities, builds runtime features, runs configured Meson tests and stages runtime files, matching Vulkan WSI layer, scripts/looks and third-party licenses under `stage/opt/onex3/gamescope/`. No target installation, application launch or session restart occurs. See [manual selection](../permanent/README.md).

`build.sh` in this directory instead applies official commits `905a89bb81c4da505312361cd5d6e28b5753ebd1` and `3521d6bf058110ea09198db9e5ca87f395c25b9e` to the same base. This earlier candidate built and passed its configured tests, but did not resolve the device pacing problem. It is retained as a separate reproducible comparison, not the accepted build.

Gamescope's MIT license accompanies the accepted patch in [accepted-runtime/LICENSE](accepted-runtime/LICENSE); staged dependencies retain their own licenses. The source pins and upstream patch identities remain in the recipes. The Lua user profile is installed separately.
