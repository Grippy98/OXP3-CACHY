"""Pure launcher tests; no native community DLL or driver is loaded."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "launcher.py"
SPEC = importlib.util.spec_from_file_location("xess_community_launcher", SOURCE)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.package = self.root / "package with spaces;$(not-a-command)'quoted"
        for name in ("lib/libvulkan_intel.so", "shim/igdext64.dll", "tools/cm-compile.sh",
                     "tools/cmk_pack.py", "igc/neo/bin/ocloc"):
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture only; never execute")
        (self.package / "igc/neo/bin/ocloc").chmod(0o700)
        (self.package / "tools/cm-compile.sh").chmod(0o700)
        (self.package / "igc/igc/local/lib").mkdir(parents=True)
        (self.package / "kernels").mkdir()
        self.runtime = self.root / "runtime"
        self.environment = {
            "HOME": str(self.root / "home"), "XDG_RUNTIME_DIR": str(self.runtime),
            "PATH": "/fixture/bin", "PROTON_ENABLE_HDR": "1", "DXVK_HDR": "1",
            "PRIVATE_SECRET": "must-not-be-printed", "OTHER_SETTING": "keep me",
        }
        self.drivers = self.root / "system drivers"
        self.drivers.mkdir()

    def manifest(self, name, library, architecture=None):
        icd = {"library_path": library}
        if architecture is not None:
            icd["library_arch"] = architecture
        path = self.drivers / name
        path.write_text(json.dumps({"ICD": icd}))
        return path

    def test_literal_paths_and_hdr_are_preserved_without_modifying_inputs(self):
        library = self.package / "lib/libvulkan_intel.so"
        originals = {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}
        original_env = dict(self.environment)
        package = launcher.checked_package(str(self.package))
        environment = launcher.launch_environment(package, self.environment, search_dirs=[])
        manifest = Path(environment["VK_DRIVER_FILES"])
        self.assertEqual(json.loads(manifest.read_text())["ICD"]["library_path"], str(library))
        self.assertEqual(environment["ANV_CM_HELPER"], str(self.package / "tools/cm-compile.sh"))
        self.assertEqual(environment["INTC_ALT_DRIVER_EXTENSIONS_PATH"],
                         "Z:" + str(self.package / "shim").replace("/", "\\"))
        for key in ("PROTON_ENABLE_HDR", "DXVK_HDR", "OTHER_SETTING", "PRIVATE_SECRET"):
            self.assertEqual(environment[key], self.environment[key])
        self.assertNotIn("IGDEXT_TRACE", environment)
        self.assertNotIn("IGDEXT_FORCE_FALLBACK", environment)
        self.assertEqual(self.environment, original_env)
        self.assertEqual({p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}, originals)
        self.assertEqual(stat_permissions(manifest), 0o600)
        self.assertEqual(stat_permissions(manifest.parent), 0o700)
        self.assertFalse((self.root / "home").exists())

    def test_existing_driver_selection_and_architectures(self):
        stock = self.manifest("intel_icd.x86_64.json", "libvulkan_intel.so", "64")
        intel32 = self.manifest("intel_icd.i686.json", "libvulkan_intel.so", "32")
        amd = self.manifest("radeon.json", "libvulkan_radeon.so", "64")
        hasvk = self.manifest("intel_hasvk.json", "libvulkan_intel_hasvk.so", "64")
        untouched = self.manifest("not-anv.json", "vendor.so")
        for path in (stock, intel32, amd, hasvk, untouched):
            path.chmod(0o444)
        selected = [stock, amd, intel32, hasvk, amd, untouched]
        self.environment["VK_DRIVER_FILES"] = os.pathsep.join(map(str, selected))
        self.environment["VK_ICD_FILENAMES"] = "/ignored/legacy.json"
        before = {p: p.read_bytes() for p in self.drivers.iterdir()}
        result = launcher.launch_environment(self.package, self.environment, search_dirs=[])
        values = result["VK_DRIVER_FILES"].split(os.pathsep)
        self.assertEqual(values[1:], list(map(str, [amd, intel32, hasvk, untouched])))
        self.assertEqual(result["VK_ICD_FILENAMES"], "/ignored/legacy.json")
        self.assertEqual({p: p.read_bytes() for p in self.drivers.iterdir()}, before)

    def test_legacy_selection_directory_expansion_and_default_additions(self):
        stock = self.manifest("intel_icd.x86_64.json", "libvulkan_intel.so")
        intel32 = self.manifest("intel_icd.i686.json", "libvulkan_intel.so")
        amd = self.manifest("radeon.json", "libvulkan_radeon.so")
        self.environment["VK_ICD_FILENAMES"] = str(self.drivers)
        self.assertEqual(launcher.retained_driver_files(self.environment), [intel32, amd])
        del self.environment["VK_ICD_FILENAMES"]
        self.environment["VK_ADD_DRIVER_FILES"] = str(amd)
        self.assertEqual(launcher.retained_driver_files(self.environment, [self.drivers]), [amd, intel32])
        self.environment["VK_DRIVER_FILES"] = ""
        self.assertEqual(launcher.retained_driver_files(self.environment, [self.drivers]), [])
        self.assertTrue(stock.exists())

    def test_missing_default_driver_directories_are_not_added_as_manifests(self):
        amd = self.manifest("radeon.json", "libvulkan_radeon.so")
        self.assertEqual(launcher.retained_driver_files(
            self.environment, [self.root / "does not exist", self.drivers]), [amd])

    def test_elf_class_and_malformed_manifests_do_not_drop_32bit_or_other_drivers(self):
        binary32 = self.drivers / "driver32/libvulkan_intel.so"
        binary64 = self.drivers / "driver64/libvulkan_intel.so"
        for binary, byte in ((binary32, b"\x01"), (binary64, b"\x02")):
            binary.parent.mkdir()
            binary.write_bytes(b"\x7fELF" + byte)
        self.assertFalse(launcher.is_64bit_anv(self.manifest("a.json", str(binary32))))
        self.assertTrue(launcher.is_64bit_anv(self.manifest("b.json", str(binary64))))
        malformed = self.drivers / "broken.json"
        for contents in ("not json", "null", "[]", '{"ICD": null}', '{"ICD": {"library_path": 8}}'):
            malformed.write_text(contents)
            self.assertFalse(launcher.is_64bit_anv(malformed))

    def test_extension_merge_and_optional_flags(self):
        self.environment["VKD3D_DISABLE_EXTENSIONS"] = "VK_EXT_other, VK_EXT_descriptor_buffer,VK_EXT_other"
        result = launcher.launch_environment(self.package, self.environment, trace=True, fallback=True, search_dirs=[])
        self.assertEqual(result["VKD3D_DISABLE_EXTENSIONS"], "VK_EXT_other,VK_EXT_descriptor_buffer")
        self.assertEqual(result["IGDEXT_TRACE"], "1")
        self.assertEqual(result["IGDEXT_FORCE_FALLBACK"], "1")

    def test_off_executes_exact_arguments_and_environment_without_package_or_writes(self):
        arguments = ["/a path/proton", "waitforexitandrun", "game;$()", "a b", "--flag=value"]
        with mock.patch.dict(os.environ, self.environment, clear=True), \
                mock.patch.object(os, "geteuid", return_value=1000), \
                mock.patch.object(os, "execvpe") as execute, \
                mock.patch.object(launcher, "checked_package", side_effect=AssertionError("package read")):
            self.assertEqual(launcher.main(["--off", "--trace", "--fallback", "--package", "/missing", "--", *arguments]), 0)
        execute.assert_called_once_with(arguments[0], arguments, self.environment)
        self.assertFalse(self.runtime.exists())

    def test_normal_exec_uses_an_argument_array_and_never_a_shell(self):
        arguments = ["/bin/game with spaces", "$(do-not-execute)", "a; b", "--child-option"]
        with mock.patch.dict(os.environ, self.environment, clear=True), \
                mock.patch.object(os, "geteuid", return_value=1000), \
                mock.patch.object(os, "execvpe") as execute:
            launcher.main(["--package", str(self.package), "--", *arguments])
        executable, argv, environment = execute.call_args.args
        self.assertEqual(executable, arguments[0])
        self.assertEqual(argv, arguments)
        self.assertEqual(environment["PROTON_ENABLE_HDR"], "1")

    def test_missing_package_files_fail_before_manifest_write_or_exec(self):
        (self.package / "shim/igdext64.dll").unlink()
        with mock.patch.dict(os.environ, self.environment, clear=True), \
                mock.patch.object(os, "geteuid", return_value=1000), \
                mock.patch.object(os, "execvpe") as execute:
            with self.assertRaisesRegex(launcher.LauncherError, "missing package file"):
                launcher.main(["--package", str(self.package), "--", "game"])
        execute.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_requires_command_and_refuses_root_or_ambiguous_probe(self):
        with mock.patch.object(os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(launcher.LauncherError, "child command is required"):
                launcher.main([])
            with self.assertRaisesRegex(launcher.LauncherError, "does not accept"):
                launcher.main(["--probe", "--", "game"])
        with mock.patch.object(os, "geteuid", return_value=0):
            with self.assertRaisesRegex(launcher.LauncherError, "not root"):
                launcher.main(["--off", "--", "game"])

    def test_print_environment_is_whitelisted_and_probe_runs_only_vulkaninfo(self):
        with mock.patch.dict(os.environ, self.environment, clear=True), \
                mock.patch.object(os, "geteuid", return_value=1000), \
                mock.patch.object(os, "execvpe") as execute:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                launcher.main(["--package", str(self.package), "--print-env"])
            printed = json.loads(output.getvalue())
            self.assertNotIn("PRIVATE_SECRET", printed)
            self.assertNotIn("OTHER_SETTING", printed)
            self.assertEqual(printed["PROTON_ENABLE_HDR"], "1")
            execute.assert_not_called()
            with contextlib.redirect_stderr(io.StringIO()) as error:
                launcher.main(["--package", str(self.package), "--probe"])
            self.assertIn("Preflight only", error.getvalue())
        self.assertEqual(execute.call_args.args[:2], ("vulkaninfo", ["vulkaninfo", "--summary"]))

    def test_reuses_icd_and_refuses_nonprivate_runtime_directory(self):
        first = launcher.write_icd(self.package, self.environment)
        before = first.stat().st_mtime_ns
        self.assertEqual(launcher.write_icd(self.package, self.environment), first)
        self.assertEqual(first.stat().st_mtime_ns, before)
        first.parent.chmod(0o755)
        with self.assertRaisesRegex(launcher.LauncherError, "private directory"):
            launcher.write_icd(self.package, self.environment)

    def test_rejects_relative_and_unrepresentable_package_paths(self):
        for value in ("relative", str(self.root / "colon:name"), str(self.root / "back\\slash")):
            with self.assertRaises(launcher.LauncherError):
                launcher.checked_package(value)


def stat_permissions(path):
    return path.stat().st_mode & 0o777


if __name__ == "__main__":
    unittest.main()
