# Intel PCON host tests

Run `sh run-tests.sh` with Python 3 and a C compiler supporting address/undefined-behavior sanitizers. Exact original/candidate function bodies are extracted from the compact `fixtures/` files into a temporary translation unit; kernel dependencies are modeled by the small harness stubs. Fixtures retain their original Intel notices and are not complete kernel sources.

The 9,598 historical checks cover strict/local capability gates, parameter values, MST/native-DP exclusions, HDMI range selection, AS-v1 construction/readback and baseline native-DP pack/unpack equivalence. The VTotal patch's transcoder writes and hardware readback, atomic ordering, real packet transmission and TV acceptance are outside these tests. The adjacent patch files are the complete build implementation; fixtures are only host-test inputs.
