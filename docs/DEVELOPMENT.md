# Development checks

From the repository root:

```sh
python3 scripts/check_repo.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The public-content check covers syntax, local links, one README/writeup per fix, and accidental artifact/private-data patterns. It skips generated build/cache directories and upstream reference documentation. It is not a complete secret scanner.

Run the component suites after changing their implementations:

```sh
bash fixes/boot-controller/tests/run-state-tests.sh
bash fixes/boot-controller/tests/run-firmware-tests.sh
bash fixes/boot-controller/tests/run-wait-tests.sh
python3 fixes/boot-controller/tests/test-controller-state.py
python3 fixes/boot-controller/tests/test-promotion-state-independent.py
python3 -m unittest discover -s fixes/intel-tdp-mangohud/tdp/tests -p 'test_*.py'
python3 -m unittest discover -s fixes/intel-tdp-mangohud/permissions/tests -p 'test_*.py'
bash fixes/intel-tdp-mangohud/telemetry/tests/run-tests.sh
```

Display adapter tests, extracted kernel-function sanitizer tests, InputPlumber schema checks and the isolated D-Bus integration tests have instructions beside their sources. The Lua suite needs Lua/LuaJIT; kernel, EFI and native package builds need their separately documented toolchains.

Host tests do not establish a working HDMI picture, controller firmware behavior, suspend/resume or an installed system transaction. Record those outcomes in concise status prose when known; keep raw device evidence outside this repository.
