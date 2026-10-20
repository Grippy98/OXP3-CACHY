#!/usr/bin/env python3
"""Independent permission-helper tests. Uses temporary files, never host sysfs."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

HELPER = Path(__file__).parents[1] / "onex3_metrics_permissions.py"
spec = importlib.util.spec_from_file_location("permissions_helper", HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="onex3-permission-review-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.powercap = self.root / "powercap"
        self.pmt = self.root / "intel_pmt"
        self.powercap.mkdir()
        self.pmt.mkdir()
        self.boot_id = self.root / "boot_id"
        self.boot_id.write_text("test-boot\n")
        self.state = self.root / "private-state/state.json"

    def zone(self, name, domain):
        path = self.powercap / name
        path.mkdir()
        (path / "name").write_text(domain + "\n")
        (path / "energy_uj").write_text("123\n")
        (path / "constraint_0_power_limit_uw").write_text("25000000\n")
        return path

    def endpoint(self, name, guid, size):
        path = self.pmt / name
        path.mkdir()
        (path / "guid").write_text(guid + "\n")
        (path / "size").write_text(str(size) + "\n")
        (path / "telem").write_bytes(bytes(size))
        return path

    def map_path(self, name):
        return {"/sys/class/powercap": self.powercap,
                "/sys/class/intel_pmt": self.pmt}.get(str(name), Path(name))

    def test_candidate_selection_does_not_include_limits_mmio_other_domains_or_guids(self):
        package = self.zone("intel-rapl:0", "package-0")
        uncore = package / "intel-rapl:0:1"
        uncore.mkdir()
        (uncore / "name").write_text("uncore\n")
        (uncore / "energy_uj").write_text("5\n")
        core = package / "intel-rapl:0:0"
        core.mkdir()
        (core / "name").write_text("core\n")
        (core / "energy_uj").write_text("6\n")
        self.zone("intel-rapl-mmio:0", "package-0")
        self.zone("intel-rapl:1", "package-1")
        good = self.endpoint("telem2", "0x03086000", 3352)
        self.endpoint("telem1", "0x03086100", 744)
        self.endpoint("telem3", "0x03086000", 3351)
        with mock.patch.object(helper, "Path", self.map_path):
            self.assertEqual(set(helper.candidates()), {path.resolve() for path in (
                package / "energy_uj", uncore / "energy_uj", good / "telem")})
        self.assertEqual((package / "constraint_0_power_limit_uw").read_text(), "25000000\n")

    def test_permission_restore_is_exact_idempotent_and_preserves_external_changes(self):
        sensors = [self.root / name for name in ("package_energy", "uncore_energy", "pmt_telem")]
        for sensor in sensors:
            sensor.write_text("read-only data\n")
        original_stat = Path.stat
        original = {str(sensors[0]): (0, 0o400), str(sensors[1]): (4, 0o600),
                    str(sensors[2]): (0, 0o640)}
        attrs = original.copy()
        calls = []

        def fake_stat(path, **kwargs):
            values = list(original_stat(path, **kwargs))
            if str(path) in attrs:
                gid, mode = attrs[str(path)]
                values[0] = stat.S_IFREG | mode
                values[4], values[5] = 0, gid
            return os.stat_result(values)

        def fake_chown(path, uid, gid):
            calls.append(("chown", str(path), uid, gid))
            self.assertEqual(uid, -1)
            attrs[str(path)] = (gid, attrs[str(path)][1])

        def fake_chmod(path, mode):
            calls.append(("chmod", str(path), mode))
            attrs[str(path)] = (attrs[str(path)][0], mode)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(helper, "STATE", self.state))
            stack.enter_context(mock.patch.object(helper, "BOOT_ID", self.boot_id))
            stack.enter_context(mock.patch.object(helper, "candidates", return_value=sensors))
            stack.enter_context(mock.patch.object(helper.grp, "getgrnam", return_value=mock.Mock(gr_gid=77)))
            stack.enter_context(mock.patch.object(Path, "stat", fake_stat))
            stack.enter_context(mock.patch.object(helper.os, "chown", fake_chown))
            stack.enter_context(mock.patch.object(helper.os, "chmod", fake_chmod))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            helper.apply()
            helper.apply()
            saved = json.loads(self.state.read_text())
            self.assertEqual(saved["nodes"], {path: {"gid": gid, "mode": mode}
                for path, (gid, mode) in original.items()})
            self.assertTrue(all(value == (77, 0o440) for value in attrs.values()))
            attrs[str(sensors[2])] = (88, 0o400)  # administrator changed this sensor
            helper.restore()
            self.assertEqual(attrs[str(sensors[0])], original[str(sensors[0])])
            self.assertEqual(attrs[str(sensors[1])], original[str(sensors[1])])
            self.assertEqual(attrs[str(sensors[2])], (88, 0o400))
            before = len(calls)
            self.boot_id.write_text("next-boot\n")
            helper.restore()
            self.assertEqual(len(calls), before)

    @contextlib.contextmanager
    def fake_permission_nodes(self):
        nodes = [self.root / name for name in ('one', 'two')]
        for node in nodes:
            node.write_text('sensor\n')
        attrs = {str(nodes[0]): (0, 0o400), str(nodes[1]): (4, 0o600)}
        original = attrs.copy()
        real_stat = Path.stat

        def fake_stat(path, **kwargs):
            values = list(real_stat(path, **kwargs))
            if str(path) in attrs:
                gid, mode = attrs[str(path)]
                values[0], values[4], values[5] = stat.S_IFREG | mode, 0, gid
            return os.stat_result(values)

        def chown(path, uid, gid):
            attrs[str(path)] = (gid, attrs[str(path)][1])

        def chmod(path, mode):
            attrs[str(path)] = (attrs[str(path)][0], mode)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(helper, 'STATE', self.state))
            stack.enter_context(mock.patch.object(helper, 'BOOT_ID', self.boot_id))
            stack.enter_context(mock.patch.object(helper, 'candidates', return_value=nodes))
            stack.enter_context(mock.patch.object(helper.grp, 'getgrnam', return_value=mock.Mock(gr_gid=77)))
            stack.enter_context(mock.patch.object(Path, 'stat', fake_stat))
            stack.enter_context(mock.patch.object(helper.os, 'chown', chown))
            stack.enter_context(mock.patch.object(helper.os, 'chmod', chmod))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield nodes, attrs, original, chmod

    def test_chmod_failure_undoes_its_chown_and_prior_changes_in_same_apply(self):
        with self.fake_permission_nodes() as (nodes, attrs, original, real_chmod):
            failed = False

            def chmod(path, mode):
                nonlocal failed
                if path == nodes[1] and mode == helper.READ_MODE and not failed:
                    failed = True
                    raise OSError('injected chmod failure after chown')
                real_chmod(path, mode)

            with mock.patch.object(helper.os, 'chmod', chmod):
                with self.assertRaisesRegex(OSError, 'changes from this attempt restored'):
                    helper.apply()
            self.assertEqual(attrs, original)
            self.assertEqual(json.loads(self.state.read_text())['pending_apply'], {})

    def test_saved_owned_intermediate_pair_is_restored_after_interrupted_apply(self):
        with self.fake_permission_nodes() as (nodes, attrs, original, real_chmod):
            with mock.patch.object(helper.os, 'chmod', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    helper.apply()
            self.assertEqual(attrs[str(nodes[0])], (77, original[str(nodes[0])][1]))
            self.assertIn(str(nodes[0]), json.loads(self.state.read_text())['pending_apply'])
            helper.restore()
            self.assertEqual(attrs, original)
            self.assertEqual(json.loads(self.state.read_text())['pending_apply'], {})

    def test_pending_apply_does_not_authorize_restoring_arbitrary_admin_attributes(self):
        with self.fake_permission_nodes() as (nodes, attrs, original, real_chmod):
            with mock.patch.object(helper.os, 'chmod', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    helper.apply()
            attrs[str(nodes[0])] = (77, 0o444)
            helper.restore()
            self.assertEqual(attrs[str(nodes[0])], (77, 0o444))

    def test_failed_retry_preserves_previous_interrupted_apply_marker(self):
        with self.fake_permission_nodes() as (nodes, attrs, original, real_chmod):
            with mock.patch.object(helper.os, 'chmod', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    helper.apply()
            with mock.patch.object(helper.os, 'chmod', side_effect=OSError('retry failed')):
                with self.assertRaisesRegex(OSError, 'changes from this attempt restored'):
                    helper.apply()
            self.assertIn(str(nodes[0]), json.loads(self.state.read_text())['pending_apply'])
            helper.restore()
            self.assertEqual(attrs, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
