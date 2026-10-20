import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("onex3_tdp", Path(__file__).parents[1] / "onex3_tdp.py")
tdp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tdp)


class RaplTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = {}
        for control, pl1 in (("intel-rapl", 25_125_000), ("intel-rapl-mmio", 35_000_000)):
            zone = self.root / f"{control}:0"
            zone.mkdir()
            (zone / "name").write_text("package-0\n")
            (zone / "enabled").write_text("1\n")
            # Intentionally use unusual and reversed constraint indices.
            for index, kind, value in ((7, "long_term", pl1), (3, "short_term", 52_000_000)):
                (zone / f"constraint_{index}_name").write_text(kind + "\n")
                path = zone / f"constraint_{index}_power_limit_uw"
                path.write_text(str(value))
                self.original[str(path)] = value
            (zone / "constraint_7_max_power_uw").write_text("25000000")
            (zone / "constraint_3_max_power_uw").write_text("0")
            (zone / "constraint_7_time_window_us").write_text("27983872")
            (zone / "constraint_3_time_window_us").write_text("976")
        ignored = self.root / "intel-rapl:0:1"
        ignored.mkdir()
        (ignored / "name").write_text("uncore")
        (ignored / "constraint_0_power_limit_uw").write_text("999")

    def backend(self):
        return tdp.RaplBackend(2, 40, self.root)

    def test_names_dual_domain_readback_and_exact_restore(self):
        backend = self.backend()
        self.assertEqual(backend.read_limit_w(), 25)
        self.assertEqual(backend.set_limit_w(17), 17)
        self.assertTrue(all(value == 17_000_000 for value in backend.snapshot().values()))
        backend.restore()
        self.assertEqual(backend.snapshot(), self.original)
        for zone in (self.root / "intel-rapl:0", self.root / "intel-rapl-mmio:0"):
            self.assertEqual((zone / "constraint_7_time_window_us").read_text(), "27983872")
            self.assertEqual((zone / "constraint_3_time_window_us").read_text(), "976")
        self.assertEqual((self.root / "intel-rapl:0:1/constraint_0_power_limit_uw").read_text(), "999")

    def test_requested_full_range_without_assuming_nominal_max_is_ceiling(self):
        backend = self.backend()
        for watts in (2, 40):
            self.assertEqual(backend.set_limit_w(watts), watts)
        backend.restore()
        self.assertEqual(backend.snapshot(), self.original)

    def test_invalid_values_do_not_touch_controls(self):
        backend = self.backend()
        for value in (0, 1, 41, -1, 17.0, True, "17"):
            with self.subTest(value=value), self.assertRaises(tdp.RaplError):
                backend.set_limit_w(value)
        self.assertEqual(backend.snapshot(), self.original)
        self.assertFalse(backend.has_requests)
        for low, high in ((2.5, 40), (2, 40.5), (True, 40), (0, 40), (40, 2)):
            with self.subTest(range=(low, high)), self.assertRaises(tdp.RaplError):
                tdp.RaplBackend(low, high, self.root)

    def test_missing_domain_and_disabled_domain_fail_closed(self):
        zone = self.root / "intel-rapl-mmio:0"
        (zone / "name").write_text("psys")
        with self.assertRaises(tdp.RaplError):
            self.backend()
        (zone / "name").write_text("package-0")
        (zone / "enabled").write_text("0")
        with self.assertRaises(tdp.RaplError):
            self.backend()

    def test_partial_write_failure_restores_all_original_values(self):
        backend = self.backend()
        original_write = backend._write
        attempts = 0

        def write(path, value):
            nonlocal attempts
            attempts += 1
            original_write(path, value)
            if attempts == 3:
                raise OSError("injected write error after partial hardware change")

        backend._write = write
        with self.assertRaisesRegex(tdp.RaplError, "previous values restored"):
            backend.set_limit_w(17)
        self.assertEqual(backend.snapshot(), self.original)

    def test_readback_mismatch_rolls_back_and_quantization_is_accepted(self):
        backend = self.backend()
        original_write = backend._write
        corrupted = False

        def write(path, value):
            nonlocal corrupted
            original_write(path, value)
            if value == 17_000_000 and not corrupted:
                corrupted = True
                path.write_text("18000000")

        backend._write = write
        with self.assertRaisesRegex(tdp.RaplError, "readback mismatch"):
            backend.set_limit_w(17)
        self.assertEqual(backend.snapshot(), self.original)
        backend._write = lambda path, value: original_write(path, value + 125_000)
        self.assertEqual(backend.set_limit_w(17), 17)
        self.assertTrue(all(value == 17_125_000 for value in backend.snapshot().values()))

    def test_restore_failure_is_reported_and_remains_retryable(self):
        backend = self.backend()
        backend.set_limit_w(17)
        original_write = backend._write
        backend._write = lambda path, value: (_ for _ in ()).throw(OSError("injected denied restore"))
        with self.assertRaises(tdp.RaplError):
            backend.restore()
        self.assertTrue(backend.has_requests)
        backend._write = original_write
        backend.restore()
        self.assertEqual(backend.snapshot(), self.original)

    def test_baseline_is_fresh_each_start_and_has_no_cross_boot_file(self):
        backend = self.backend()
        backend.set_limit_w(17)
        backend.restore()
        changed = self.root / "intel-rapl:0/constraint_7_power_limit_uw"
        changed.write_text("28000000")
        fresh = self.backend()
        fresh.set_limit_w(12)
        fresh.restore()
        self.assertEqual(tdp.read_number(changed), 28_000_000)

    def test_device_guard_uses_both_vendor_and_product(self):
        dmi = self.root / "dmi"
        dmi.mkdir()
        (dmi / "sys_vendor").write_text("ONE-NETBOOK\n")
        (dmi / "product_name").write_text("ONEXPLAYER 3\n")
        tdp.check_device(dmi)
        (dmi / "product_name").write_text("ONEXPLAYER X1")
        with self.assertRaises(tdp.RaplError):
            tdp.check_device(dmi)

    def test_final_snapshot_failure_also_rolls_back_hardware_writes(self):
        backend = self.backend()
        real_snapshot = backend.snapshot
        calls = 0

        def snapshot():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected read error in final snapshot")
            return real_snapshot()

        backend.snapshot = snapshot
        with self.assertRaisesRegex(tdp.RaplError, "previous values restored"):
            backend.set_limit_w(17)
        self.assertEqual(real_snapshot(), self.original)

    def test_success_uses_verified_snapshot_instead_of_a_later_reread(self):
        backend = self.backend()
        backend.read_limit_w = lambda: (_ for _ in ()).throw(OSError("late read should not occur"))
        self.assertEqual(backend.set_limit_w(17), 17)
        self.assertTrue(all(value == 17_000_000 for value in backend.snapshot().values()))
        backend.restore()

    def test_manager_notify_start_post_is_ready_but_starting_is_not(self):
        import subprocess
        cases = [
            ("active", "running", "notify-reload", True),
            ("activating", "start-post", "notify-reload", True),
            ("activating", "start", "notify-reload", False),
            ("activating", "start-post", "simple", False),
            ("inactive", "dead", "notify-reload", False),
        ]
        for active, substate, unit_type, expected in cases:
            result = subprocess.CompletedProcess(
                [], 0, f"ActiveState={active}\nSubState={substate}\nType={unit_type}\n"
            )
            with self.subTest(state=(active, substate, unit_type)), \
                    patch.object(tdp.pwd, "getpwnam", return_value=type("Account", (), {"pw_uid": 1234})()), \
                    patch.object(tdp.subprocess, "run", return_value=result):
                self.assertEqual(tdp.manager_active("test-user"), expected)


if __name__ == "__main__":
    unittest.main()
