"""Filesystem/process/extraction contracts; no DLL or upstream script is run."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("vkd3d_installer", Path(__file__).parents[1] / "install-vkd3d.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
REAL_REFUSE_RUNNING = installer.refuse_running
CORE = b"test Core bytes: never executed"


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "GTA path;$(literal)"
        self.game.mkdir()
        (self.game / "GTA5_Enhanced.exe").write_bytes(b"game fixture")
        self.target = self.game / installer.TARGET
        self.busy = mock.patch.object(installer, "refuse_running").start()
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(installer, "CORE_SHA256", installer.sha(CORE)).start()
        self.release = mock.patch.object(installer, "release_core", return_value=CORE).start()

    @property
    def state_path(self):
        return self.game / installer.STATE_DIR / "state.json"

    def state(self):
        return json.loads(self.state_path.read_text())

    def test_file_case_permissions_backup_idempotence_and_scoped_writes(self):
        self.target = self.game / "D3D12Core.DLL"
        self.target.write_bytes(b"original Core")
        self.target.chmod(0o751)
        untouched = {name: b"preserved " + name.encode() for name in
                     ("d3d12.dll", "OptiScaler.ini", "settings.xml")}
        for name, contents in untouched.items():
            (self.game / name).write_bytes(contents)
        installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), CORE)
        self.assertEqual(self.state()["target_name"], self.target.name)
        backup = self.state_path.parent / "original.dll"
        original_backup = (backup.read_bytes(), backup.stat().st_mtime_ns)
        self.release.reset_mock()
        installer.install(self.game, self.root / "nonexistent archive")
        self.release.assert_not_called()
        self.assertEqual((backup.read_bytes(), backup.stat().st_mtime_ns), original_backup)
        installer.rollback(self.game)
        self.assertEqual(self.target.read_bytes(), b"original Core")
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o751)
        for name, contents in untouched.items():
            self.assertEqual((self.game / name).read_bytes(), contents)

    def test_absent_original_is_removed_and_rollback_is_idempotent(self):
        installer.install(self.game)
        self.assertEqual(installer.check(self.game)[1], 0)
        installer.rollback(self.game)
        self.assertFalse(self.target.exists())
        self.assertEqual(installer.check(self.game)[1], 1)
        self.assertIn("Already rolled back", installer.rollback(self.game))
        installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), CORE)
        self.assertEqual(self.state()["original"], {"kind": "absent"})

    def test_relative_and_dangling_symlinks_restore_verbatim_without_following(self):
        external = self.root / "outside.dll"
        external.write_bytes(b"must not change")
        for link in ("../outside.dll", "missing-relative.dll"):
            with self.subTest(link=link):
                game = self.root / ("game" + str(len(list(self.root.iterdir()))))
                game.mkdir()
                target = game / installer.TARGET
                target.symlink_to(link)
                installer.install(game)
                self.assertFalse(target.is_symlink())
                installer.rollback(game)
                self.assertTrue(target.is_symlink())
                self.assertEqual(os.readlink(target), link)
                self.assertEqual(external.read_bytes(), b"must not change")

    def test_case_collision_is_refused_before_release_or_backup(self):
        self.target.write_bytes(b"one")
        (self.game / "D3D12CORE.DLL").write_bytes(b"two")
        # Case-insensitive filesystems cannot represent this fixture.
        if len([p for p in self.game.iterdir() if p.name.casefold() == installer.TARGET]) < 2:
            self.skipTest("case-insensitive test filesystem")
        with self.assertRaises(installer.InstallError):
            installer.install(self.game)
        self.release.assert_not_called()
        self.assertFalse(self.state_path.exists())

    def test_modified_core_or_substituted_symlink_blocks_rollback(self):
        installer.install(self.game)
        self.target.write_bytes(b"user update")
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.game)
        self.assertEqual(self.target.read_bytes(), b"user update")
        outside = self.root / "pinned.dll"
        outside.write_bytes(CORE)
        self.target.unlink()
        self.target.symlink_to(outside)
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.game)
        self.assertTrue(self.target.is_symlink())

    def test_backup_corruption_and_recorded_foreign_game_are_refused(self):
        self.target.write_bytes(b"original")
        installer.install(self.game)
        state = self.state()
        state["game_dir"] = str(self.root / "different game")
        self.state_path.write_text(json.dumps(state))
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.game)
        state["game_dir"] = str(self.game)
        self.state_path.write_text(json.dumps(state))
        (self.state_path.parent / "original.dll").write_bytes(b"corrupted")
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.game)
        self.assertEqual(self.target.read_bytes(), CORE)

    def test_symlinked_state_directory_or_state_file_is_refused(self):
        external = self.root / "foreign"
        external.mkdir()
        state_dir = self.game / installer.STATE_DIR
        state_dir.symlink_to(external, target_is_directory=True)
        with self.assertRaises(installer.InstallError):
            installer.install(self.game)
        state_dir.unlink()
        installer.install(self.game)
        stored = self.state_path.read_bytes()
        self.state_path.unlink()
        (external / "state.json").write_bytes(stored)
        self.state_path.symlink_to(external / "state.json")
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.game)

    def test_check_is_read_only_and_requires_no_download(self):
        before = sorted(self.game.iterdir())
        self.assertEqual(installer.check(self.game)[1], 1)
        self.assertEqual(sorted(self.game.iterdir()), before)
        self.release.assert_not_called()

    def test_release_failure_does_not_create_backup_or_change_target(self):
        self.target.write_bytes(b"original")
        self.release.side_effect = installer.InstallError("bad archive")
        with self.assertRaises(installer.InstallError):
            installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertFalse((self.game / installer.STATE_DIR).exists())

    def test_failed_atomic_install_preserves_original_and_prepared_backup(self):
        self.target.write_bytes(b"original")
        real_atomic = installer.atomic_bytes
        def fail_target(path, data, mode=0o600):
            if path == self.target:
                raise OSError("simulated publication failure")
            return real_atomic(path, data, mode)
        with mock.patch.object(installer, "atomic_bytes", side_effect=fail_target):
            with self.assertRaises(OSError):
                installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(self.state()["status"], "prepared")
        self.assertEqual((self.state_path.parent / "original.dll").read_bytes(), b"original")
        installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), CORE)

    def test_restore_before_failed_state_write_can_be_finalized_without_overwrite(self):
        self.target.write_bytes(b"original")
        installer.install(self.game)
        with mock.patch.object(installer, "save_state", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                installer.rollback(self.game)
        self.assertEqual(self.target.read_bytes(), b"original")
        with mock.patch.object(installer, "atomic_bytes", wraps=installer.atomic_bytes) as writes:
            installer.rollback(self.game)
        self.assertTrue(all(call.args[0] != self.target for call in writes.call_args_list))
        self.assertEqual(self.state()["status"], "rolled_back")

    def test_published_core_before_failed_state_write_keeps_original_backup(self):
        self.target.write_bytes(b"original")
        real_save = installer.save_state
        def interrupted(game, state):
            if state["status"] == "installed":
                raise OSError("simulated interruption after Core publication")
            real_save(game, state)
        with mock.patch.object(installer, "save_state", side_effect=interrupted):
            with self.assertRaises(OSError):
                installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), CORE)
        self.assertEqual(self.state()["status"], "prepared")
        self.release.reset_mock()
        installer.install(self.game)
        self.release.assert_not_called()
        installer.rollback(self.game)
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_lock_contention_refuses_file_replacement(self):
        self.target.write_bytes(b"original")
        with mock.patch.object(installer.fcntl, "flock", side_effect=BlockingIOError):
            with self.assertRaises(installer.InstallError):
                installer.install(self.game)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertFalse(self.state_path.exists())

    def test_malformed_state_reports_controlled_errors(self):
        installer.install(self.game)
        good = self.state()
        for bad in ([], {**good, "original": []}, {**good, "target_name": "../escape.dll"}):
            with self.subTest(bad=bad):
                self.state_path.write_text(json.dumps(bad))
                with self.assertRaises(installer.InstallError):
                    installer.load_state(self.game)

    def test_busy_guard_precedes_all_cli_actions(self):
        self.busy.side_effect = installer.InstallError("GTA running")
        for action in ("check", "install", "rollback"):
            with self.subTest(action=action), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(installer.main([action, "--game-dir", str(self.game)]), 2)
        self.release.assert_not_called()
        self.assertFalse((self.game / installer.STATE_DIR).exists())

    def test_game_directory_must_contain_executable_and_defaults_are_unambiguous(self):
        self.assertEqual(installer.checked_game(str(self.game)), self.game.resolve())
        with self.assertRaises(installer.InstallError):
            installer.checked_game(str(self.root))
        with mock.patch.object(Path, "home", return_value=self.root):
            with self.assertRaises(installer.InstallError):
                installer.checked_game(None)
            for prefix in (".local/share/Steam", ".steam/steam"):
                game = self.root / prefix / "steamapps/common/Grand Theft Auto V Enhanced"
                game.mkdir(parents=True)
                (game / "GTA5_Enhanced.exe").write_bytes(b"fixture")
            with self.assertRaises(installer.InstallError):
                installer.checked_game(None)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_special_target_is_refused_without_blocking(self):
        os.mkfifo(self.target)
        with self.assertRaises(installer.InstallError):
            installer.snapshot(self.target)


class ArchiveAndProcessTests(unittest.TestCase):
    def test_download_is_official_bounded_and_does_not_execute_anything(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "release"
            with mock.patch.object(installer.urllib.request, "urlopen", return_value=io.BytesIO(b"release")) as opened:
                installer.download(path)
            self.assertEqual(path.read_bytes(), b"release")
            self.assertEqual(opened.call_args.args[0].full_url, installer.ASSET_URL)
            self.assertEqual(opened.call_args.kwargs["timeout"], 30)
            path.unlink()
            with mock.patch.object(installer, "MAX_ARCHIVE", 4), \
                    mock.patch.object(installer.urllib.request, "urlopen", return_value=io.BytesIO(b"too large")):
                with self.assertRaises(installer.InstallError):
                    installer.download(path)

    def test_invalid_archive_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "archive.tar.zst"
            archive.write_bytes(b"tampered archive")
            with self.assertRaises(installer.InstallError), mock.patch.object(subprocess, "run") as run:
                installer.verified_archive(archive)
            run.assert_not_called()

    def test_extraction_uses_only_fixed_regular_core_and_argument_arrays(self):
        listing = f"-rwxr-xr-x  0 user group 1 Jan 1 00:00 {installer.MEMBER}\n".encode()
        results = [subprocess.CompletedProcess([], 0, listing), subprocess.CompletedProcess([], 0, CORE)]
        with mock.patch.object(installer.shutil, "which", return_value="/trusted path/bsdtar"), \
                mock.patch.object(installer, "CORE_SHA256", installer.sha(CORE)), \
                mock.patch.object(subprocess, "run", side_effect=results) as run:
            self.assertEqual(installer.extract_core(Path("/literal archive;$()")), CORE)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][-2:], ["--", installer.MEMBER])
            self.assertNotIn("shell", call.kwargs)
            self.assertIn("/literal archive;$()", call.args[0])
            self.assertFalse(any("setup_vkd3d" in argument for argument in call.args[0]))

    def test_archive_links_duplicates_and_wrong_core_are_rejected(self):
        for listing in (f"lrwxrwxrwx {installer.MEMBER} -> elsewhere\n",
                        f"-rw {installer.MEMBER}\n-rw {installer.MEMBER}\n",
                        f"drwx {installer.MEMBER}\n"):
            with self.subTest(listing=listing), \
                    mock.patch.object(installer.shutil, "which", return_value="bsdtar"), \
                    mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, listing.encode())) as run:
                with self.assertRaises(installer.InstallError):
                    installer.extract_core(Path("archive"))
                self.assertEqual(run.call_count, 1)
        listing = f"-rw {installer.MEMBER}\n".encode()
        with mock.patch.object(installer.shutil, "which", return_value="bsdtar"), \
                mock.patch.object(subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0, listing),
                                                                  subprocess.CompletedProcess([], 0, b"wrong Core")]):
            with self.assertRaises(installer.InstallError):
                installer.extract_core(Path("archive"))

    def test_gnu_tar_zstd_fallback_has_no_shell(self):
        tools = {"bsdtar": None, "tar": "/usr/bin/tar", "zstd": "/usr/bin/zstd"}
        listing = f"-rw {installer.MEMBER}\n".encode()
        with mock.patch.object(installer.shutil, "which", side_effect=tools.get), \
                mock.patch.object(installer, "CORE_SHA256", installer.sha(CORE)), \
                mock.patch.object(subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0, listing),
                                                                  subprocess.CompletedProcess([], 0, CORE)]) as run:
            installer.extract_core(Path("archive"))
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/tar")
        self.assertIn("--use-compress-program=/usr/bin/zstd", run.call_args.args[0])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_proc_detection_handles_windows_paths_case_and_truncated_comm(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            entry = proc / "123"
            entry.mkdir()
            (entry / "cmdline").write_bytes(b"wine\0Z:\\game\\GTA5_ENHANCED.EXE\0")
            (entry / "comm").write_text("wine\n")
            with self.assertRaises(installer.InstallError):
                REAL_REFUSE_RUNNING(proc)
            (entry / "cmdline").unlink()
            (entry / "comm").write_text("GTA5_Enhanced.ex\n")
            with self.assertRaises(installer.InstallError):
                REAL_REFUSE_RUNNING(proc)
            (entry / "comm").write_text("unrelated\n")
            REAL_REFUSE_RUNNING(proc)


if __name__ == "__main__":
    unittest.main()
