"""Scanner regressions using fake credentials and temporary Git repositories only."""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class WorktreeScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        spec = importlib.util.spec_from_file_location("scanner", Path(__file__).with_name("b_worktree_value_scan.py"))
        self.scanner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.scanner)
        self.repo_patch = patch.object(self.scanner, "REPO", self.root)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)
        self.git(self.root, "init", "-b", "master")
        (self.root / ".gitignore").write_text("backend/.env\ncontrol.txt\n", encoding="utf-8")
        self.git(self.root, "add", ".gitignore")
        (self.root / "backend").mkdir()
        self.values = {key: "fake-scanner-value-" + key for key in self.scanner.CENSUS_KEYS}
        self.envfile = self.root / "backend/.env"
        self.envfile.write_text("\n".join(f"{key}={value}" for key, value in self.values.items()), encoding="utf-8")

    @staticmethod
    def git(root, *args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout

    def run_scan(self, root=None):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["scanner", "--root", str(root or self.root)]),
            contextlib.redirect_stdout(output),
        ):
            rc = self.scanner.main()
        return rc, output.getvalue()

    def test_quoted_paths_are_actually_scanned(self):
        for name in ("中文.txt", "ASCII space.txt", "中文 空格.txt"):
            (self.root / name).write_text(self.values["ADMIN_PASSWORD"], encoding="utf-8")
        rc, output = self.run_scan()
        self.assertEqual(rc, 0)
        self.assertIn("含值文件=3", output)
        for name in ("中文.txt", "ASCII space.txt", "中文 空格.txt"):
            self.assertIn(f"命中 {name}", output)
        for value in self.values.values():
            self.assertNotIn(value, output)

    def test_git_enumeration_uses_requested_root(self):
        other = self.root / "other"
        other.mkdir()
        self.git(other, "init", "-b", "master")
        (other / "leak.txt").write_text(self.values["ADMIN_PASSWORD"], encoding="utf-8")
        rc, output = self.run_scan(other)
        self.assertEqual(rc, 0)
        self.assertIn("命中 leak.txt", output.split("[B] 面", 1)[0])

    def test_partial_input_is_rejected(self):
        self.envfile.write_text("ADMIN_PASSWORD=" + self.values["ADMIN_PASSWORD"], encoding="utf-8")
        rc, output = self.run_scan()
        self.assertNotEqual(rc, 0)
        self.assertNotIn("VERDICT: 尺子活着", output)

    def test_empty_input_value_is_rejected(self):
        lines = [f"{key}={value if key != 'JWT_SECRET' else ''}" for key, value in self.values.items()]
        self.envfile.write_text("\n".join(lines), encoding="utf-8")
        self.assertNotEqual(self.run_scan()[0], 0)

    def test_dotenv_quotes_and_inline_comments_are_parsed(self):
        self.envfile.write_text(
            "\n".join(f'{key}="{value}" # fake comment' for key, value in self.values.items()), encoding="utf-8"
        )
        self.assertEqual(self.scanner.load_values(), {key: value.encode() for key, value in self.values.items()})

    def test_unreadable_file_prevents_success(self):
        unreadable = self.root / "unreadable.txt"
        unreadable.write_text("fixture", encoding="utf-8")
        original = self.scanner.scan
        with patch.object(
            self.scanner,
            "scan",
            side_effect=lambda path, needles: {"UNREADABLE": 1} if path == unreadable else original(path, needles),
        ):
            rc, output = self.run_scan()
        self.assertNotEqual(rc, 0)
        self.assertNotIn("VERDICT: 尺子活着", output)

    def test_directory_enumeration_error_prevents_success(self):
        original_walk = os.walk
        blocked = self.root / self.values["JWT_SECRET"] / "blocked"

        def failing_walk(root, **kwargs):
            callback = kwargs.get("onerror")
            if callback:
                callback(PermissionError(13, "FAKE_SENSITIVE_DIRECTORY", str(blocked)))
            yield from original_walk(root)

        with patch.object(self.scanner.os, "walk", side_effect=failing_walk):
            rc, output = self.run_scan()
        self.assertEqual(rc, 3)
        self.assertIn("阶段=B/目录枚举", output)
        self.assertIn("PermissionError", output)
        self.assertIn("[REDACTED]/blocked", output)
        self.assertNotIn("FAKE_SENSITIVE_DIRECTORY", output)
        self.assertNotIn(self.values["JWT_SECRET"], output)

    def test_git_failure_does_not_print_sensitive_stderr(self):
        result = subprocess.CompletedProcess([], 128, "", "FAKE_SENSITIVE_STDERR")
        with patch.object(self.scanner, "git", return_value=result):
            output = io.StringIO()
            with patch.object(sys, "argv", ["scanner"]), contextlib.redirect_stdout(output):
                try:
                    rc = self.scanner.main()
                except SystemExit as exc:
                    rc = exc.code
        self.assertNotEqual(rc, 0)
        self.assertIn("阶段=A/Git枚举", output.getvalue())
        self.assertIn("Git rc=128", output.getvalue())
        self.assertNotIn("FAKE_SENSITIVE_STDERR", output.getvalue())

    def test_git_start_failure_is_diagnostic_and_sanitized(self):
        error = FileNotFoundError(2, "FAKE_SENSITIVE_GIT_START", "git")
        with patch.object(self.scanner, "git", side_effect=error):
            rc, output = self.run_scan()
        self.assertEqual(rc, 3)
        self.assertIn("阶段=A/Git枚举", output)
        self.assertIn("FileNotFoundError", output)
        self.assertNotIn("FAKE_SENSITIVE_GIT_START", output)

    def test_unreadable_paths_are_diagnostic_and_redacted(self):
        unreadable = self.root / (self.values["ADMIN_PASSWORD"] + " 空格.txt")
        unreadable.write_text("fixture", encoding="utf-8")
        original_open = open
        for blocked, tag, relative in (
            (unreadable, "A", "[REDACTED] 空格.txt"),
            (self.envfile, "B", "backend/.env"),
        ):

            def guarded_open(path, mode="r", *args, _blocked=blocked, **kwargs):
                if Path(path) == _blocked and mode == "rb":
                    raise PermissionError(13, "FAKE_SENSITIVE_READ", str(_blocked))
                return original_open(path, mode, *args, **kwargs)

            with self.subTest(tag=tag):
                with patch("builtins.open", side_effect=guarded_open):
                    rc, output = self.run_scan()
                self.assertEqual(rc, 3)
                self.assertIn(f"[{tag}] 读取失败 {relative!r}", output)
                self.assertNotIn(self.values["ADMIN_PASSWORD"], output)
                self.assertNotIn("FAKE_SENSITIVE_READ", output)

    def test_zero_positive_control_is_not_clean(self):
        other = self.root / "empty-tree"
        other.mkdir()
        self.git(other, "init", "-b", "master")
        self.assertEqual(self.run_scan(other)[0], 2)

    def test_sensitive_value_in_hit_path_is_not_printed(self):
        secret = self.values["ADMIN_PASSWORD"]
        (self.root / (secret + ".txt")).write_text(secret, encoding="utf-8")
        rc, output = self.run_scan()
        self.assertEqual(rc, 0)
        self.assertNotIn(secret, output)

    def test_unreadable_ignored_file_prevents_success(self):
        original = self.scanner.scan
        with patch.object(
            self.scanner,
            "scan",
            side_effect=lambda path, needles: {"UNREADABLE": 1} if path == self.envfile else original(path, needles),
        ):
            rc, output = self.run_scan()
        self.assertEqual(rc, 3)
        self.assertNotIn("VERDICT: 尺子活着", output)

    def test_inaccessible_root_fails_without_sensitive_traceback(self):
        for method in ("resolve", "is_dir"):
            with (
                self.subTest(method=method),
                patch.object(self.scanner.Path, method, side_effect=PermissionError("FAKE_SENSITIVE_ROOT")),
            ):
                rc, output = self.run_scan()
                self.assertEqual(rc, 3)
                self.assertNotIn("FAKE_SENSITIVE_ROOT", output)


if __name__ == "__main__":
    unittest.main()
