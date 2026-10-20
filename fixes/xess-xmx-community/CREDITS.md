# Component credits and licenses

- Community implementation: [HHHHanasak1/xess-xmx-linux at the pinned source](https://github.com/HHHHanasak1/xess-xmx-linux/tree/627566641c360c7a0e5d529898b2a81daef1c7ab), including contributions by kas5852. [MIT notice](licenses/community-MIT.txt).
- Shim base and Intel extension headers: [GameTechDev/dxvk-igdext](https://github.com/GameTechDev/dxvk-igdext). [Intel MIT notice](licenses/dxvk-igdext-MIT.txt). Retain notices in the pinned shim source.
- Mesa ANV and its dependencies keep their upstream licenses. The source archive's [license overview](licenses/Mesa-license.rst) identifies the applicable notices; keep the complete source/build notices with redistributed binaries.
- [Intel Graphics Compiler](https://github.com/intel/intel-graphics-compiler/tree/v2.10.10) and [Intel compute-runtime](https://github.com/intel/compute-runtime/tree/25.18.33578.6) are fetched from official releases. The private package preserves their distribution notices; they are not vendored here.
- [LLVM-MinGW](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261006) is a build toolchain with its own component licenses. Do not redistribute it without its notices.
- Games supply their own proprietary Intel XeSS, XeFG and XeLL libraries. This collection does not redistribute those libraries or generated game kernels.

The original community code is not relicensed. New launcher/build glue in this folder uses the MIT license with copyright 2026 Grippy98; that declaration does not transfer authorship of any upstream component.
