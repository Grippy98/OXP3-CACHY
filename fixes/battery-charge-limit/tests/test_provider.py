#!/usr/bin/env python3
"""Synthetic sysfs tests. No real battery, system bus or EC is accessed."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


spec = importlib.util.spec_from_file_location("charge_limit_provider", Path(__file__).parents[1] / "charge-limit-provider.py")
provider = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provider)


class BatteryFixture:
    def __init__(self, directory):
        self.root = Path(directory)
        dmi = self.root / "sys/class/dmi/id"
        dmi.mkdir(parents=True)
        (dmi / "sys_vendor").write_text("ONE-NETBOOK\n")
        (dmi / "product_name").write_text("ONEXPLAYER 3\n")
        self.acpi = self.root / "sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:00/device:00/PNP0C09:00/PNP0C0A:00"
        self.battery = self.acpi / "power_supply/BAT0"
        self.battery.mkdir(parents=True)
        (self.battery / "type").write_text("Battery\n")
        self.threshold = self.battery / provider.ATTRIBUTE
        self.threshold.write_text("80\n")
        self.behaviour = self.battery / provider.BEHAVIOUR_ATTRIBUTE
        self.behaviour_writes = []
        self.set_kernel_mode("inhibit-charge-awake")
        supply = self.root / "sys/class/power_supply"
        supply.mkdir(parents=True)
        (supply / "BAT0").symlink_to(self.battery)
        driver = self.root / "sys/bus/platform/drivers/acpi-battery/PNP0C0A:00"
        driver.mkdir(parents=True)
        (driver / "firmware_node").symlink_to(self.acpi)

    def backend(self):
        backend = provider.ChargeLimitBackend(self.root)
        write_behaviour = backend._write_behaviour

        def emulate_kernel_write(mode):
            write_behaviour(mode)
            self.behaviour_writes.append(self.behaviour.read_text())
            # A real sysfs file renders the supported list on subsequent reads.
            self.set_kernel_mode(mode)

        backend._write_behaviour = emulate_kernel_write
        return backend

    def set_kernel_mode(self, mode):
        self.behaviour.write_text(" ".join(f"[{item}]" if item == mode else item for item in ("auto", "inhibit-charge", "inhibit-charge-awake")) + "\n")


class ProviderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="charge-limit-")
        self.addCleanup(temporary.cleanup)
        self.fixture = BatteryFixture(temporary.name)

    def test_probe_preserves_existing_firmware_cap(self):
        before = self.fixture.threshold.stat().st_mtime_ns
        backend = self.fixture.backend()
        self.assertEqual(backend.status(), {
            "supported": True, "battery": "BAT0", "raw_threshold_percent": 80,
            "max_charge_level": 80, "suggested_minimum_limit": 50,
            "charge_behaviour": {"mode": "inhibit-charge-awake", "supported_modes": ["auto", "inhibit-charge", "inhibit-charge-awake"]},
        })
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, before)

    def test_valid_limits_include_integer_values_and_safe_reset(self):
        backend = self.fixture.backend()
        for request, raw, result in [(50, 50, 50), (73, 73, 73), (99, 99, 99), (-1, 100, -1), (100, 100, -1), (80, 80, 80)]:
            with self.subTest(request=request):
                self.assertEqual(backend.set_limit(request), result)
                self.assertEqual(self.fixture.threshold.read_text(), f"{raw}\n")
                self.assertEqual(backend.read_limit(), result)

    def test_invalid_requests_never_open_for_write(self):
        backend = self.fixture.backend()
        with mock.patch.object(backend, "_open_threshold", wraps=backend._open_threshold) as opened:
            for value in (-2, 0, 1, 49, 101, True, False, 80.0, "80", None):
                with self.subTest(value=value), self.assertRaises(provider.ChargeLimitError):
                    backend.set_limit(value)
            self.assertEqual(opened.call_count, 0)
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")

    def test_no_write_for_unchanged_cap_or_unlimited(self):
        backend = self.fixture.backend()
        with mock.patch.object(backend, "_open_threshold", wraps=backend._open_threshold) as opened:
            backend.set_limit(80)
            self.assertTrue(all(not args.args[0] & os.O_WRONLY for args in opened.call_args_list))
        self.fixture.threshold.write_text("100\n")
        with mock.patch.object(backend, "_open_threshold", wraps=backend._open_threshold) as opened:
            self.assertEqual(backend.set_limit(-1), -1)
            self.assertTrue(all(not args.args[0] & os.O_WRONLY for args in opened.call_args_list))

    def test_absent_threshold_does_not_advertise_support_or_create_file(self):
        self.fixture.threshold.unlink()
        with self.assertRaises(FileNotFoundError):
            self.fixture.backend()
        self.assertFalse(self.fixture.threshold.exists())

    def test_bad_firmware_value_does_not_become_fake_support(self):
        for raw in ("0", "49", "101", "", "unknown", "80 90"):
            with self.subTest(raw=raw):
                self.fixture.threshold.write_text(raw)
                with self.assertRaises(provider.ChargeLimitError):
                    self.fixture.backend()
                self.assertEqual(self.fixture.threshold.read_text(), raw)

    def test_exact_dmi_whitelist(self):
        for field, value in (("sys_vendor", "Other"), ("product_name", "ONEXPLAYER 2")):
            path = self.fixture.root / "sys/class/dmi/id" / field
            original = path.read_text()
            with self.subTest(field=field):
                path.write_text(value)
                with self.assertRaises(provider.ChargeLimitError):
                    self.fixture.backend()
                path.write_text(original)

    def test_acpi_binding_required(self):
        (self.fixture.root / provider.ACPI_BATTERY_PATHS[0]).unlink()
        with self.assertRaises(provider.ChargeLimitError):
            self.fixture.backend()

    def test_legacy_acpi_binding_is_supported(self):
        (self.fixture.root / provider.ACPI_BATTERY_PATHS[0]).unlink()
        legacy = self.fixture.root / provider.ACPI_BATTERY_PATHS[1]
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(self.fixture.acpi)
        self.assertEqual(self.fixture.backend().read_limit(), 80)

    def test_different_power_supply_is_refused(self):
        (self.fixture.battery / "type").write_text("Mains\n")
        with self.assertRaises(provider.ChargeLimitError):
            self.fixture.backend()

    def test_threshold_symlink_cannot_write_another_file(self):
        other = self.fixture.root / "unrelated"
        other.write_text("KEEP\n")
        self.fixture.threshold.unlink()
        self.fixture.threshold.symlink_to(other)
        with self.assertRaises(provider.ChargeLimitError):
            self.fixture.backend()
        self.assertEqual(other.read_text(), "KEEP\n")

    def test_identity_and_threshold_are_revalidated_before_write(self):
        backend = self.fixture.backend()
        (self.fixture.root / "sys/class/dmi/id/product_name").write_text("Other")
        with self.assertRaises(provider.ChargeLimitError):
            backend.set_limit(60)
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")

    def test_readback_mismatch_is_not_reported_as_success(self):
        backend = self.fixture.backend()
        with mock.patch.object(backend, "read_raw", side_effect=[80, 80]):
            with self.assertRaisesRegex(provider.ChargeLimitError, "did not confirm"):
                backend.set_limit(65)
        # No implicit restore to 80 is attempted after an uncertain write.
        self.assertEqual(self.fixture.threshold.read_text(), "65\n")

    def test_read_and_write_failures_propagate(self):
        backend = self.fixture.backend()
        with mock.patch.object(backend, "_open_threshold", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                backend.read_limit()
            with self.assertRaises(PermissionError):
                backend.set_limit(60)

    def test_remote_config_matches_exported_abi(self):
        import tomllib
        config = Path(__file__).parents[1] / "rootfs/etc/steamos-manager/remotes.d/onex3-charge-limit.toml"
        self.assertEqual(tomllib.loads(config.read_text()), {"BatteryChargeLimit1": {
            "bus_name": provider.BUS_NAME, "object_path": provider.OBJECT_PATH,
        }})

    def test_status_and_check_have_no_cli_write_argument(self):
        backend = self.fixture.backend()
        with mock.patch("sys.argv", ["charge-limit-provider.py", "status"]), mock.patch.object(provider, "ChargeLimitBackend", return_value=backend), mock.patch("builtins.print") as output:
            self.assertEqual(provider.main(), 0)
        self.assertEqual(json.loads(output.call_args.args[0])["max_charge_level"], 80)
        with mock.patch("sys.argv", ["charge-limit-provider.py", "check"]), mock.patch.object(provider, "ChargeLimitBackend", return_value=backend), mock.patch("builtins.print"):
            self.assertEqual(provider.main(), 0)
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")

    def test_behaviour_uses_actual_kernel_modes_and_bracketed_selection(self):
        backend = self.fixture.backend()
        before = self.fixture.behaviour.stat().st_mtime_ns
        self.assertEqual(backend.read_behaviour(), {
            "mode": "inhibit-charge-awake", "supported_modes": ["auto", "inhibit-charge", "inhibit-charge-awake"],
        })
        self.assertEqual(backend.status()["charge_behaviour"]["mode"], "inhibit-charge-awake")
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, before)
        self.assertEqual(self.fixture.behaviour_writes, [])

    def test_modes_write_only_explicit_text_and_never_the_ceiling(self):
        backend = self.fixture.backend()
        before = self.fixture.threshold.stat().st_mtime_ns
        for mode in ("auto", "inhibit-charge", "inhibit-charge-awake"):
            self.assertEqual(backend.set_behaviour(mode), mode)
            self.assertEqual(backend.read_behaviour()["mode"], mode)
        self.assertEqual(self.fixture.behaviour_writes, ["auto\n", "inhibit-charge\n", "inhibit-charge-awake\n"])
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")
        self.assertEqual(self.fixture.threshold.stat().st_mtime_ns, before)

    def test_ceiling_changes_never_write_bypass(self):
        backend = self.fixture.backend()
        before = self.fixture.behaviour.stat().st_mtime_ns
        backend.set_limit(-1)
        backend.set_limit(65)
        self.assertEqual(backend.read_behaviour()["mode"], "inhibit-charge-awake")
        self.assertEqual(self.fixture.behaviour.stat().st_mtime_ns, before)
        self.assertEqual(self.fixture.behaviour_writes, [])

    def test_unchanged_mode_and_invalid_requests_never_write(self):
        backend = self.fixture.backend()
        self.assertEqual(backend.set_behaviour("inhibit-charge-awake"), "inhibit-charge-awake")
        for mode in ("", "force-discharge", "AUTO", "auto\n", "[auto]", "auto;reboot", None, 0):
            with self.subTest(mode=mode), self.assertRaises(provider.ChargeLimitError):
                backend.set_behaviour(mode)
        self.assertEqual(self.fixture.behaviour_writes, [])

    def test_behaviour_parser_refuses_malformed_or_unknown_capabilities(self):
        backend = self.fixture.backend()
        for value in ("", "auto inhibit-charge", "[auto] [inhibit-charge]", "[auto] auto", "[auto] force-discharge", "[auto", "[auto]]", "[auto]\n" + "x" * 513):
            with self.subTest(value=value):
                self.fixture.behaviour.write_text(value)
                with self.assertRaises(provider.ChargeLimitError):
                    backend.read_behaviour()
                self.assertIsNone(backend.optional_behaviour())
                self.assertEqual(backend.read_limit(), 80)

    def test_only_reported_behaviour_can_be_requested(self):
        backend = self.fixture.backend()
        self.fixture.behaviour.write_text("[auto]\n")
        self.assertEqual(backend.read_behaviour(), {"mode": "auto", "supported_modes": ["auto"]})
        with self.assertRaisesRegex(provider.ChargeLimitError, "not supported"):
            backend.set_behaviour("inhibit-charge")
        self.assertEqual(self.fixture.behaviour_writes, [])

    def test_absent_behaviour_keeps_independent_ceiling_support(self):
        self.fixture.behaviour.unlink()
        backend = self.fixture.backend()
        self.assertIsNone(backend.status()["charge_behaviour"])
        self.assertEqual(backend.read_limit(), 80)
        with self.assertRaises(FileNotFoundError):
            backend.set_behaviour("auto")
        self.assertFalse(self.fixture.behaviour.exists())

    def test_behaviour_symlink_and_changed_identity_are_refused(self):
        backend = self.fixture.backend()
        other = self.fixture.root / "unrelated"
        other.write_text("[auto]\n")
        self.fixture.behaviour.unlink()
        self.fixture.behaviour.symlink_to(other)
        with self.assertRaises(provider.ChargeLimitError):
            backend.set_behaviour("inhibit-charge")
        self.assertEqual(other.read_text(), "[auto]\n")
        self.fixture.behaviour.unlink()
        self.fixture.set_kernel_mode("inhibit-charge-awake")
        (self.fixture.root / "sys/class/dmi/id/product_name").write_text("Other")
        with self.assertRaises(provider.ChargeLimitError):
            backend.set_behaviour("auto")
        self.assertEqual(self.fixture.behaviour_writes, [])

    def test_behaviour_readback_mismatch_is_error_without_implicit_restore(self):
        backend = self.fixture.backend()
        before = backend.read_behaviour()
        with mock.patch.object(backend, "read_behaviour", side_effect=[before, before]):
            with self.assertRaisesRegex(provider.ChargeLimitError, "did not confirm"):
                backend.set_behaviour("auto")
        self.assertEqual(self.fixture.behaviour_writes, ["auto\n"])
        self.assertEqual(self.fixture.threshold.read_text(), "80\n")


if __name__ == "__main__":
    unittest.main()
