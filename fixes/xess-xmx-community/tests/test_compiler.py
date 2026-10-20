"""Synthetic Debian archives only: no network or downloaded executable runs."""

import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "fetch-compiler.py"
SPEC = importlib.util.spec_from_file_location("xess_compiler_fetch", SOURCE)
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)
ELF = b"\x7fELF\x02fixture only; never execute"


def tar_payload(entries, compression="gz"):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:" + compression) as archive:
        for name, contents, mode in entries:
            member = tarfile.TarInfo(name)
            member.mode = mode
            if isinstance(contents, tuple):
                member.type = contents[0]
                member.linkname = contents[1]
                archive.addfile(member)
            else:
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
    return output.getvalue()


def deb_archive(payload, member="data.tar.gz"):
    output = bytearray(b"!<arch>\n")
    for name, contents in (("debian-binary", b"2.0\n"),
                           ("control.tar.gz", gzip.compress(b"fixture control; never run")),
                           (member, payload)):
        header = (f"{name:<16}{0:<12}{0:<6}{0:<6}{0o100644:<8o}{len(contents):<10}`\n").encode()
        if len(header) != 60:
            raise AssertionError("invalid ar fixture header")
        output.extend(header + contents)
        if len(contents) % 2:
            output.extend(b"\n")
    return bytes(output)


class Response(io.BytesIO):
    def geturl(self):
        return "https://fixtures.invalid/data.deb"


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.package = self.root / "private package;$(no-command)'quoted"
        self.package.mkdir()
        (self.package / "keep.txt").write_text("preserve existing package payload")
        self.core = [
            ("./usr/local/lib/libigc.so.2", (tarfile.SYMTYPE, "libigc.so.2.fixture"), 0o777),
            ("./usr/local/lib/libigc.so.2.fixture", ELF, 0o644),
            ("./usr/local/lib/libiga64.so.2", ELF, 0o644),
            ("./usr/local/lib/igc2/NOTICES.txt", b"Intel license fixture", 0o644),
        ]
        self.opencl = [
            ("./usr/local/lib/libigdfcl.so.2", ELF, 0o644),
            ("./usr/local/lib/libopencl-clang2.so.15", ELF, 0o644),
        ]
        self.neo = [
            ("./usr/bin/ocloc-25.18.1", ELF, 0o755),
            ("./usr/lib/x86_64-linux-gnu/libocloc.so", ELF, 0o644),
            ("./usr/share/doc/intel-ocloc/copyright", b"Intel license fixture", 0o644),
        ]

    def fixtures(self, groups=None):
        groups = groups or [self.core, self.opencl, self.neo]
        archives = [deb_archive(tar_payload(entries, "xz" if index == 1 else "gz"),
                                "data.tar.xz" if index == 1 else "data.tar.gz")
                    for index, entries in enumerate(groups)]
        assets = tuple(compiler.Asset(f"fixture-{i}.deb", f"https://fixtures.invalid/{i}",
                                      hashlib.sha256(data).hexdigest(), "neo" if i == 2 else "igc")
                       for i, data in enumerate(archives))
        by_url = {asset.url: data for asset, data in zip(assets, archives)}
        return assets, by_url

    def install(self, groups=None):
        assets, by_url = self.fixtures(groups)
        with mock.patch.object(compiler, "ASSETS", assets), \
                mock.patch.object(compiler, "open_https", side_effect=lambda url: Response(by_url[url])):
            return compiler.install_compiler(self.package)

    def assert_clean_failure(self):
        self.assertFalse(os.path.lexists(self.package / "igc"))
        self.assertEqual(sorted(p.name for p in self.package.iterdir()), ["keep.txt"])
        self.assertEqual((self.package / "keep.txt").read_text(), "preserve existing package payload")

    def test_exact_public_intel_assets_are_pinned(self):
        self.assertEqual(len(compiler.ASSETS), 3)
        for asset in compiler.ASSETS:
            self.assertTrue(asset.url.startswith("https://github.com/intel/"))
            self.assertRegex(asset.sha256, r"^[0-9a-f]{64}$")
        self.assertIn("v2.10.10", compiler.ASSETS[0].url)
        self.assertIn("25.18.33578.6", compiler.ASSETS[2].url)

    def test_success_retains_tree_links_licenses_and_provenance_without_execution(self):
        real_run = subprocess.run
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            self.assertEqual(command[0], "ar")
            self.assertNotIn("shell", kwargs)
            return real_run(command, **kwargs)

        with mock.patch.object(compiler.subprocess, "run", side_effect=run):
            result = self.install()
        self.assertEqual(result, self.package / "igc")
        self.assertTrue((result / "igc/local/lib/libigc.so.2").is_symlink())
        self.assertEqual((result / "igc/local/lib/libigc.so.2").read_bytes(), ELF)
        self.assertTrue(os.access(result / "neo/bin/ocloc-25.18.1", os.X_OK))
        self.assertIn("Intel license", (result / "igc/local/lib/igc2/NOTICES.txt").read_text())
        self.assertIn("Intel license", (result / "neo/share/doc/intel-ocloc/copyright").read_text())
        self.assertEqual(len(json.loads((result / "compiler-sources.json").read_text())["assets"]), 3)
        self.assertEqual(len(commands), 6)
        self.assertEqual(sorted(p.name for p in self.package.iterdir()), ["igc", "keep.txt"])

    def test_checksum_failure_prevents_ar_and_cleans_staging(self):
        assets, by_url = self.fixtures()
        corrupted = b"unexpected replacement content"
        with mock.patch.object(compiler, "ASSETS", assets), \
                mock.patch.object(compiler, "open_https", return_value=Response(corrupted)), \
                mock.patch.object(compiler.subprocess, "run") as run:
            with self.assertRaisesRegex(compiler.CompilerError, "SHA-256 mismatch"):
                compiler.install_compiler(self.package)
        run.assert_not_called()
        self.assert_clean_failure()

    def test_download_failure_after_first_asset_leaves_no_partial_bundle(self):
        assets, by_url = self.fixtures()

        def response(url):
            if url == assets[1].url:
                raise OSError("fixture connection failed")
            return Response(by_url[url])

        with mock.patch.object(compiler, "ASSETS", assets), mock.patch.object(compiler, "open_https", side_effect=response):
            with self.assertRaisesRegex(OSError, "connection failed"):
                compiler.install_compiler(self.package)
        self.assert_clean_failure()

    def test_existing_empty_directory_and_broken_symlink_are_preserved_without_network(self):
        target = self.package / "igc"
        with mock.patch.object(compiler, "open_https") as fetch:
            target.mkdir()
            with self.assertRaisesRegex(compiler.CompilerError, "already exists"):
                compiler.install_compiler(self.package)
            self.assertTrue(target.is_dir())
            target.rmdir()
            target.symlink_to(self.root / "absent")
            with self.assertRaisesRegex(compiler.CompilerError, "already exists"):
                compiler.install_compiler(self.package)
            self.assertTrue(target.is_symlink())
        fetch.assert_not_called()

    def test_traversal_absolute_symlink_and_special_members_are_rejected(self):
        bad_entries = [
            ("../outside", b"bad", 0o644),
            ("/absolute", b"bad", 0o644),
            ("./usr/escape", (tarfile.SYMTYPE, "/etc/passwd"), 0o777),
            ("./usr/escape", (tarfile.SYMTYPE, "../../outside"), 0o777),
            ("./usr/escape", (tarfile.LNKTYPE, "etc/passwd"), 0o644),
            ("./usr/fifo", (tarfile.FIFOTYPE, ""), 0o644),
        ]
        for entry in bad_entries:
            with self.subTest(entry=entry[0]):
                with self.assertRaises((compiler.CompilerError, tarfile.FilterError)):
                    self.install([[*self.core, entry], self.opencl, self.neo])
                self.assert_clean_failure()
                self.assertFalse((self.root / "outside").exists())

    def test_collisions_and_missing_or_nonelf_binaries_do_not_publish(self):
        collision = ("./usr/local/lib/libiga64.so.2", b"different", 0o644)
        for groups in ([self.core, [*self.opencl, collision], self.neo],
                       [self.core, self.opencl, self.neo[1:]],
                       [self.core, [*self.opencl[:-1], (self.opencl[-1][0], b"wrong binary", 0o644)], self.neo]):
            with self.assertRaises(compiler.CompilerError):
                self.install(groups)
            self.assert_clean_failure()

    def test_publish_race_does_not_replace_an_empty_existing_target(self):
        real_publish = compiler.publish_noreplace

        def race(source, target):
            target.mkdir()
            real_publish(source, target)

        with mock.patch.object(compiler, "publish_noreplace", side_effect=race):
            with self.assertRaisesRegex(compiler.CompilerError, "appeared during preparation"):
                self.install()
        self.assertTrue((self.package / "igc").is_dir())
        self.assertEqual(list((self.package / "igc").iterdir()), [])
        self.assertFalse(any(self.package.glob(".igc-stage-*")))

    def test_nonhttps_initial_or_redirect_urls_are_rejected(self):
        with self.assertRaisesRegex(compiler.CompilerError, "must use HTTPS"):
            compiler.open_https("http://example.invalid/compiler")
        with self.assertRaisesRegex(compiler.CompilerError, "non-HTTPS asset redirect"):
            compiler.HTTPSRedirectsOnly().redirect_request(None, None, 302, "", {}, "http://example.invalid/redirect")

    def test_zstd_fallback_decompresses_to_a_staged_tar_before_filtered_extraction(self):
        work = self.root / "zstd fixture"
        work.mkdir()
        archive_path = work / "fixture.deb"
        archive_path.write_bytes(deb_archive(b"fixture-zstd", "data.tar.zst"))
        raw_tar = tar_payload(self.neo, "")
        real_open, real_run = tarfile.open, subprocess.run

        def open_tar(path, *args, **kwargs):
            if Path(path).suffix == ".zst":
                raise tarfile.ReadError("fixture Python without zstd")
            return real_open(path, *args, **kwargs)

        def run(command, **kwargs):
            if command[0] == "zstd":
                self.assertEqual(command[1:3], ["--decompress", "--stdout"])
                kwargs["stdout"].write(raw_tar)
                return subprocess.CompletedProcess(command, 0)
            return real_run(command, **kwargs)

        with mock.patch.object(compiler.tarfile, "open", side_effect=open_tar), \
                mock.patch.object(compiler.subprocess, "run", side_effect=run):
            compiler.unpack_deb_payload(archive_path, work / "usr", work)
        self.assertEqual((work / "usr/bin/ocloc-25.18.1").read_bytes(), ELF)

    def test_relative_package_is_rejected_and_help_has_no_network(self):
        with self.assertRaisesRegex(compiler.CompilerError, "absolute path"):
            compiler.install_compiler(Path("relative"))
        with mock.patch.object(compiler, "open_https") as fetch, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_result:
                compiler.main(["--help"])
        self.assertEqual(exit_result.exception.code, 0)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
