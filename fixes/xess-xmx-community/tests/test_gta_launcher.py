"""GTA profile contract tests; no game, driver or community DLL is executed."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "gta-launch.py"
SPEC = importlib.util.spec_from_file_location("gta_xess_profile", SOURCE)
profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile)


class GtaProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def hdr_wsi(self, directory=None):
        directory = directory or self.root / "private HDR WSI;$(literal)"
        directory.mkdir(parents=True)
        for name in profile.HDR_WSI_FILES:
            (directory / name).write_bytes(b"fixture: never loaded or executed")
        return directory

    def test_dxgi_replacement_retains_grouped_and_unrelated_wine_rules(self):
        original = "*DXGI.dll,d3d11=b;winmm=n,b; dxgi =b;odd-rule;nvapi64="
        merged = profile.merge_dxgi_override(original)
        self.assertEqual(merged, "d3d11=b;winmm=n,b;odd-rule;nvapi64=;dxgi=n,b")
        self.assertEqual(profile.merge_dxgi_override(merged), merged)
        self.assertEqual(profile.merge_dxgi_override(""), "dxgi=n,b")

    def test_default_profile_is_per_child_and_preserves_other_configuration(self):
        original = {"HOME": "/fixture/home", "PROTON_ENABLE_HDR": "1", "DXVK_HDR": "1",
                    "VKD3D_DISABLE_EXTENSIONS": "VK_EXT_other", "ENABLE_GAMESCOPE_WSI": "1",
                    "WINEDLLOVERRIDES": "winmm=n,b;dxgi=b", "OTHER_SETTING": "keep"}
        before = dict(original)
        result = profile.profile_environment(original)
        self.assertEqual(original, before)
        self.assertEqual(result["MESA"], "26.1")
        self.assertEqual(result["DISABLE_GAMESCOPE_WSI"], "1")
        self.assertEqual(result["WINEDLLOVERRIDES"], "winmm=n,b;dxgi=n,b")
        for key in ("PROTON_ENABLE_HDR", "DXVK_HDR", "VKD3D_DISABLE_EXTENSIONS",
                    "ENABLE_GAMESCOPE_WSI", "OTHER_SETTING"):
            self.assertEqual(result[key], original[key])

    def test_explicit_mesa_is_preserved_while_gta_wsi_disable_is_applied(self):
        result = profile.profile_environment({"MESA": "26.3", "DISABLE_GAMESCOPE_WSI": "0"})
        self.assertEqual(result["MESA"], "26.3")
        self.assertEqual(result["DISABLE_GAMESCOPE_WSI"], "1")

    def test_hdr_default_uses_mapping_home_and_removes_every_disable_value(self):
        home = self.root / "mapped home"
        directory = self.hdr_wsi(home / profile.HDR_WSI_DIRECTORY)
        for disable in (None, "", "0", "1", "anything"):
            original = {"HOME": str(home)}
            if disable is not None:
                original["DISABLE_GAMESCOPE_WSI"] = disable
            before = dict(original)
            with self.subTest(disable=disable):
                result = profile.profile_environment(original, hdr=True)
                self.assertEqual(original, before)
                self.assertNotIn("DISABLE_GAMESCOPE_WSI", result)
                self.assertEqual(result["ENABLE_GAMESCOPE_WSI"], "1")
                self.assertEqual(result["VK_ADD_IMPLICIT_LAYER_PATH"], str(directory))
                self.assertEqual(result["MESA"], "26.1")

    def test_hdr_override_is_first_deduplicated_and_preserves_existing_configuration(self):
        directory = self.hdr_wsi()
        original = {"OXP3_GTA_HDR_WSI": str(directory), "MESA": "26.3",
                    "DISABLE_GAMESCOPE_WSI": "0", "ENABLE_GAMESCOPE_WSI": "0",
                    "VK_ADD_IMPLICIT_LAYER_PATH": f"/other:{directory}:/third:/other",
                    "PROTON_ENABLE_HDR": "1", "DXVK_HDR": "1", "OTHER_SETTING": "keep",
                    "WINEDLLOVERRIDES": "winmm=n,b;*DXGI,d3d11=b"}
        before = {path: path.read_bytes() for path in directory.iterdir()}
        result = profile.profile_environment(original, hdr=True)
        self.assertEqual(result["VK_ADD_IMPLICIT_LAYER_PATH"], f"{directory}:/other:/third")
        self.assertEqual(result["WINEDLLOVERRIDES"], "winmm=n,b;d3d11=b;dxgi=n,b")
        self.assertNotIn("DISABLE_GAMESCOPE_WSI", result)
        for key in ("OXP3_GTA_HDR_WSI", "MESA", "PROTON_ENABLE_HDR", "DXVK_HDR", "OTHER_SETTING"):
            self.assertEqual(result[key], original[key])
        self.assertEqual({path: path.read_bytes() for path in directory.iterdir()}, before)

    def test_hdr_tilde_override_uses_mapping_home_without_shell_expansion(self):
        home = self.root / "mapped home"
        directory = self.hdr_wsi(home / "custom WSI;$()")
        result = profile.profile_environment(
            {"HOME": str(home), "OXP3_GTA_HDR_WSI": "~/custom WSI;$()"}, hdr=True)
        self.assertEqual(result["VK_ADD_IMPLICIT_LAYER_PATH"], str(directory))

    def test_hdr_requires_both_private_files_and_rejects_ambiguous_layer_paths(self):
        directory = self.hdr_wsi()
        for name in profile.HDR_WSI_FILES:
            file = directory / name
            contents = file.read_bytes()
            file.unlink()
            with self.subTest(missing=name), self.assertRaisesRegex(profile.ProfileError, name):
                profile.profile_environment({"OXP3_GTA_HDR_WSI": str(directory)}, hdr=True)
            file.write_bytes(contents)
        for path in ("relative", "/ambiguous:path", "/line\nbreak"):
            with self.subTest(path=path), self.assertRaises(profile.ProfileError):
                profile.profile_environment({"OXP3_GTA_HDR_WSI": path}, hdr=True)

    def test_sdr_does_not_require_or_alter_the_optional_hdr_layer(self):
        original = {"OXP3_GTA_HDR_WSI": "/missing", "VK_ADD_IMPLICIT_LAYER_PATH": "/existing"}
        result = profile.profile_environment(original)
        self.assertEqual(result["DISABLE_GAMESCOPE_WSI"], "1")
        self.assertEqual(result["VK_ADD_IMPLICIT_LAYER_PATH"], "/existing")

    def test_command_and_package_are_forwarded_as_literal_arguments(self):
        execute = mock.Mock(return_value=0)
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        original = {"HOME": "/fixture/home", "OXP3_XESS_PACKAGE": "/a path/runtime;$(literal)"}
        arguments = ["/a path/proton", "waitforexitandrun", "game;$()", "a b", "-nobattleye"]
        with mock.patch.dict(sys.modules, {"launcher": generic}), \
                mock.patch.dict(os.environ, original, clear=True):
            self.assertEqual(profile.main(arguments), 0)
            self.assertEqual(os.environ["DISABLE_GAMESCOPE_WSI"], "1")
        execute.assert_called_once_with(["--package", original["OXP3_XESS_PACKAGE"], "--", *arguments])

    def test_hdr_flag_and_optional_separator_preserve_literal_child_arguments(self):
        directory = self.hdr_wsi()
        arguments = ["/a path/proton", "waitforexitandrun", "game;$()", "a b", "--hdr"]
        for separator in ([], ["--"]):
            execute = mock.Mock(return_value=0)
            generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
            original = {"OXP3_GTA_HDR_WSI": str(directory), "DISABLE_GAMESCOPE_WSI": "0",
                        "OXP3_XESS_PACKAGE": "/a path/runtime;$(literal)"}
            with self.subTest(separator=separator), \
                    mock.patch.dict(sys.modules, {"launcher": generic}), \
                    mock.patch.dict(os.environ, original, clear=True):
                self.assertEqual(profile.main(["--hdr", *separator, *arguments]), 0)
                self.assertNotIn("DISABLE_GAMESCOPE_WSI", os.environ)
                self.assertEqual(os.environ["ENABLE_GAMESCOPE_WSI"], "1")
                self.assertEqual(os.environ["VK_ADD_IMPLICIT_LAYER_PATH"], str(directory))
            execute.assert_called_once_with(
                ["--package", original["OXP3_XESS_PACKAGE"], "--", *arguments])

    def test_separator_allows_a_literal_command_named_hdr(self):
        execute = mock.Mock(return_value=0)
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        with mock.patch.dict(sys.modules, {"launcher": generic}), \
                mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(profile.main(["--", "--hdr", "literal"]), 0)
            self.assertEqual(os.environ["DISABLE_GAMESCOPE_WSI"], "1")
        self.assertEqual(execute.call_args.args[0][-3:], ["--", "--hdr", "literal"])

    def test_missing_hdr_files_fail_before_launch_or_environment_mutation(self):
        execute = mock.Mock()
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        original = {"OXP3_GTA_HDR_WSI": str(self.root / "missing"), "DISABLE_GAMESCOPE_WSI": "0"}
        with mock.patch.dict(sys.modules, {"launcher": generic}), \
                mock.patch.dict(os.environ, original, clear=True), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(profile.main(["--hdr", "game"]), 2)
            self.assertEqual(dict(os.environ), original)
        self.assertIn("missing private HDR WSI file", output.getvalue())
        execute.assert_not_called()

    def test_legacy_general_launcher_default_is_not_used_for_the_gta_profile(self):
        execute = mock.Mock(return_value=0)
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        with mock.patch.dict(sys.modules, {"launcher": generic}), \
                mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(Path, "home", return_value=Path("/fixture/home")):
            profile.main(["game"])
        execute.assert_called_once_with(
            ["--package", "/fixture/home/.local/lib/oxp3-xess-community/20261104", "--", "game"])

    def test_no_command_does_not_launch_or_modify_the_environment(self):
        execute = mock.Mock()
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        for arguments in ([], ["--"], ["--hdr"], ["--hdr", "--"]):
            with self.subTest(arguments=arguments), \
                    mock.patch.dict(sys.modules, {"launcher": generic}), \
                    mock.patch.dict(os.environ, {"UNCHANGED": "yes"}, clear=True), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(profile.main(arguments), 2)
                self.assertEqual(dict(os.environ), {"UNCHANGED": "yes"})
        execute.assert_not_called()

    def test_launcher_errors_are_reported_without_executing_a_fallback_game(self):
        execute = mock.Mock(side_effect=RuntimeError("missing private package"))
        generic = SimpleNamespace(main=execute, LauncherError=RuntimeError)
        with mock.patch.dict(sys.modules, {"launcher": generic}), \
                mock.patch.dict(os.environ, {}, clear=True), \
                contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(profile.main(["game"]), 2)
        self.assertIn("missing private package", output.getvalue())
        execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
