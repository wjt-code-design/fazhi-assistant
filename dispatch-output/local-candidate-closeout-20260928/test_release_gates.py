"""Offline regression checks; fixtures and Git writes stay in temporary directories."""

import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.m = load("b_build_snapshot")
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"TEMP": str(self.root)}))
        self.stack.enter_context(patch.object(self.m, "REPO", self.root))
        self.git("init", "-b", "master")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        paths = [*self.m.TRIM_FILES, *(d + "/fixture.txt" for d in self.m.TRIM_DIRS)]
        for name in paths:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("fixture\n", encoding="utf-8")
        ci = self.root / self.m.CI_PATH
        ci.parent.mkdir(parents=True)
        ci.write_text("on:\n  push:\n    branches: [main, master]\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("branch", self.m.CANDIDATE)
        (self.root / "backend").mkdir()
        self.values = {k: "fixture-only-value-" + k for k in self.m.CENSUS_KEYS}
        # Old code couples the positive control to this historical password.
        old = self.root / "old.txt"
        old.write_text(self.values["ADMIN_PASSWORD"], encoding="utf-8")
        self.git("add", "old.txt")
        self.git("commit", "-m", "old fixture")
        self.stack.enter_context(
            patch.object(
                self.m, "POSITIVE_REF", self.git("rev-parse", "HEAD"), create=True
            )
        )
        self.git("rm", "old.txt")
        self.git("commit", "-m", "remove fixture")
        self.envfile = self.root / "backend/.env"
        self.envfile.write_text(
            "\n".join(f"{k}={v}" for k, v in self.values.items()), encoding="utf-8"
        )

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def run_gate(self, *args):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["builder", *args]),
            contextlib.redirect_stdout(output),
        ):
            try:
                rc = self.m.main()
            except SystemExit as exc:
                rc = exc.code
        return rc, output.getvalue()

    def test_missing_credentials_fail(self):
        self.envfile.unlink()
        rc, _ = self.run_gate("--dry-run")
        self.assertNotEqual(rc, 0)

    def test_one_missing_key_fails(self):
        self.values.pop("JWT_SECRET")
        with patch.object(self.m, "load_values", return_value=self.values):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_git_remove_failure_stops(self):
        original = self.m.git

        def fail_remove(*args, **kwargs):
            if "--force-remove" in args:
                return subprocess.CompletedProcess(args, 128, "", "injected index lock")
            return original(*args, **kwargs)

        with patch.object(self.m, "git", side_effect=fail_remove):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_silent_remove_failure_detected(self):
        original = self.m.git

        def skip_remove(*args, **kwargs):
            if "--force-remove" in args:
                return subprocess.CompletedProcess(args, 0, "", "")
            return original(*args, **kwargs)

        with patch.object(self.m, "git", side_effect=skip_remove):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_rotated_password_still_scans(self):
        self.values["ADMIN_PASSWORD"] = "fixture-rotated-password"
        with patch.object(self.m, "load_values", return_value=self.values):
            self.assertEqual(self.run_gate("--dry-run")[0], 0)

    def test_credential_in_snapshot_rejected(self):
        (self.root / "leak.txt").write_text(
            self.values["LLM_API_KEY"], encoding="utf-8"
        )
        self.git("add", "leak.txt")
        self.git("commit", "-m", "fixture leak")
        self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_unicode_credential_detected_under_windows_legacy_encoding(self):
        self.values["ADMIN_PASSWORD"] = "fixture-中文-口令"
        (self.root / "leak.txt").write_text(
            self.values["ADMIN_PASSWORD"], encoding="utf-8"
        )
        self.git("add", "leak.txt")
        self.git("commit", "-m", "unicode fixture leak")
        with (
            patch.object(self.m, "load_values", return_value=self.values),
            patch.object(subprocess, "_text_encoding", return_value="gbk"),
        ):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_dotenv_inline_comment_cannot_hide_credential(self):
        self.envfile.write_text(
            "\n".join(f"{k}={v} # local fixture" for k, v in self.values.items()),
            encoding="utf-8",
        )
        (self.root / "leak.txt").write_text(
            self.values["LLM_API_KEY"], encoding="utf-8"
        )
        self.git("add", "leak.txt")
        self.git("commit", "-m", "comment fixture leak")
        self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_dotenv_preserves_hash_inside_quotes(self):
        self.envfile.write_text(
            'ADMIN_PASSWORD="fixture#literal" # comment\n', encoding="utf-8"
        )
        self.assertEqual(self.m.load_values()["ADMIN_PASSWORD"], "fixture#literal")

    def test_unresolved_dotenv_reference_stops(self):
        self.values["LLM_API_KEY"] = "${FIXTURE_EXTERNAL_KEY}"
        with patch.object(self.m, "load_values", return_value=self.values):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_default_cannot_move_ref_without_approved_tree(self):
        self.assertNotEqual(self.run_gate()[0], 0)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "show-ref",
                "--verify",
                "refs/heads/" + self.m.BRANCH,
            ],
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_approved_tree_updates_ref_and_changed_tree_is_rejected(self):
        rc, out = self.run_gate("--dry-run")
        self.assertEqual(rc, 0)
        tree = re.search(r"--expected-tree ([0-9a-f]{40,64})", out).group(1)
        self.assertEqual(self.run_gate("--expected-tree", tree)[0], 0)
        ref = "refs/heads/" + self.m.BRANCH
        frozen = self.git("rev-parse", ref)
        self.assertEqual(self.git("rev-parse", ref + "^{tree}"), tree)
        (self.root / "new.txt").write_text("new unreviewed content", encoding="utf-8")
        self.git("add", "new.txt")
        self.git("commit", "-m", "drift")
        self.assertNotEqual(self.run_gate("--expected-tree", tree)[0], 0)
        self.assertEqual(self.git("rev-parse", ref), frozen)

    def test_scanner_error_does_not_pass(self):
        original = self.m.git

        def error(*args, **kwargs):
            if "-f" in args:
                return subprocess.CompletedProcess(args, 128, "", "fixture failure")
            return original(*args, **kwargs)

        with patch.object(self.m, "git", side_effect=error):
            self.assertNotEqual(self.run_gate("--dry-run")[0], 0)

    def test_index_environment_restored(self):
        with patch.dict(os.environ, {"GIT_INDEX_FILE": "caller-index"}):
            self.assertEqual(self.run_gate("--dry-run")[0], 0)
            self.assertEqual(os.environ["GIT_INDEX_FILE"], "caller-index")


class CollectionTests(unittest.TestCase):
    def run_case(self, results):
        m = load("b_snapshot_trim_diff")
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(m, "EVIDENCE", Path(tmp)))
            stack.enter_context(
                patch.object(m.tempfile, "gettempdir", return_value=tmp)
            )
            stack.enter_context(patch.object(m, "expand"))
            stack.enter_context(patch.object(m, "size_of", return_value=0))
            stack.enter_context(patch.object(m, "collect", side_effect=results))
            stack.enter_context(
                patch.object(
                    m.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
                )
            )
            stack.enter_context(
                patch.object(
                    sys, "argv", ["diff", "--full", "fake1", "--trim", "fake2"]
                )
            )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return m.main()

    def reading(self, rc=0, node="tests/test_a.py::test_ok"):
        return {
            "rc": rc,
            "collected": 1,
            "errors": [],
            "error_total": 0,
            "nodeids": [node],
        }

    def test_both_failed_is_not_pass(self):
        self.assertNotEqual(self.run_case([self.reading(2), self.reading(2)]), 0)

    def test_same_count_different_tests_is_not_pass(self):
        self.assertNotEqual(
            self.run_case(
                [self.reading(), self.reading(node="tests/test_b.py::test_ok")]
            ),
            0,
        )

    def test_same_successful_collection_passes(self):
        self.assertEqual(self.run_case([self.reading(), self.reading()]), 0)

    def test_missing_nodeids_does_not_pass(self):
        reading = self.reading()
        reading.pop("nodeids")
        self.assertNotEqual(self.run_case([reading.copy(), reading.copy()]), 0)

    def test_real_pytest_collection_parser(self):
        m = load("b_snapshot_trim_diff")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            backend.mkdir()
            (backend / "test_fixture.py").write_text(
                "def test_fixture():\n    assert True\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""},
            ):
                result = m.collect(root, root)
            self.assertEqual(result["rc"], 0)
            self.assertEqual(result["collected"], 1)
            self.assertEqual(result["nodeids"], ["test_fixture.py::test_fixture"])


class SuiteTests(unittest.TestCase):
    def run_case(self, collect_rc=0, test_rc=0, failures=0, probe_rc=0):
        m = load("b_probe_run_suite")
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            root = Path(tmp)
            (root / "backend").mkdir()
            stack.enter_context(patch.dict(os.environ, {"TEMP": tmp}))
            stack.enter_context(patch.object(m, "EVIDENCE", root))
            stack.enter_context(patch.object(m, "PY", Path(sys.executable)))

            def process(args, **kwargs):
                if "-c" in args:
                    return subprocess.CompletedProcess(args, 0, "3.11 9.1", "")
                if "--collect-only" in args:
                    return subprocess.CompletedProcess(
                        args, collect_rc, "1 test collected", ""
                    )
                xml = Path(
                    next(
                        a.split("=", 1)[1] for a in args if a.startswith("--junit-xml=")
                    )
                )
                child = '<failure message="fixture"/>' if failures else ""
                xml.write_text(
                    f'<testsuite><testcase name="fixture">{child}</testcase></testsuite>',
                    encoding="utf-8",
                )
                Path(kwargs["env"]["PROBE_OUT"]).write_text(
                    json.dumps(
                        {
                            "targets": [],
                            "imports_watched": [],
                            "net_events": {},
                            "net_event_kinds": 0,
                            "net_event_total": 0,
                            "pytest_exitstatus": probe_rc,
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(args, test_rc, "fixture run", "")

            stack.enter_context(patch.object(m.subprocess, "run", side_effect=process))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return m.main([tmp])

    def test_collection_failure_stops(self):
        self.assertNotEqual(self.run_case(collect_rc=2), 0)

    def test_pytest_failure_fails_gate(self):
        self.assertNotEqual(self.run_case(test_rc=1), 0)

    def test_junit_failure_fails_gate(self):
        self.assertNotEqual(self.run_case(failures=1), 0)

    def test_success_passes(self):
        self.assertEqual(self.run_case(), 0)

    def test_probe_failure_fails_gate(self):
        self.assertNotEqual(self.run_case(probe_rc=1), 0)


class EvidenceIsolationTests(unittest.TestCase):
    """The four probe drivers must be able to write a new round elsewhere.

    Without this, re-running them overwrites the historical readings the recalculator
    compares against, and "fresh evidence" silently becomes "the old numbers again".
    """

    OLD = Path(__file__).resolve().parent
    IMPORTABLE = ("b_probe_build_tree", "b_probe_run_suite", "b_probe_claim_check")
    OVERRIDE = "B_PROBE_EVIDENCE_DIR"

    def dir_state(self):
        return sorted(
            (str(p.relative_to(self.OLD)), p.stat().st_mtime_ns, p.stat().st_size)
            for p in self.OLD.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        )

    def constant_from_source(self, module_file, name, env_value):
        """Evaluate one module-level assignment without importing the module.

        b_probe_app_paths.py sets env vars, creates work dirs and installs the probe at
        import time, so importing it just to read a constant would run the experiment.
        """
        tree = ast.parse(Path(module_file).read_text(encoding="utf-8"))
        node = next(
            n
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(getattr(t, "id", None) == name for t in n.targets)
        )
        env = dict(os.environ)
        env.pop(self.OVERRIDE, None)
        if env_value is not None:
            env[self.OVERRIDE] = env_value
        ns = {
            "Path": Path,
            "os": type("os", (), {"environ": env})(),
            "__file__": str(module_file),
        }
        return eval(compile(ast.Expression(node.value), "<constant>", "eval"), ns)

    def test_override_moves_readings_into_this_rounds_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in self.IMPORTABLE:
                with patch.dict(os.environ, {self.OVERRIDE: tmp}):
                    self.assertEqual(load(name).EVIDENCE, Path(tmp), name)
            # app_paths derives PROBE_OUT from EVIDENCE, so pin the same constant by source.
            self.assertEqual(
                self.constant_from_source(
                    self.OLD / "b_probe_app_paths.py", "EVIDENCE", tmp
                ),
                Path(tmp),
            )

    def test_default_still_points_at_the_historical_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            for name in self.IMPORTABLE:
                self.assertEqual(load(name).EVIDENCE, self.OLD, name)
        for name in (*self.IMPORTABLE, "b_probe_app_paths"):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    self.constant_from_source(
                        self.OLD / f"{name}.py", "EVIDENCE", None
                    ),
                    self.OLD,
                    name,
                )

    def test_app_driver_writes_only_where_told_and_leaves_history_alone(self):
        before = self.dir_state()
        with (
            tempfile.TemporaryDirectory() as evidence,
            tempfile.TemporaryDirectory() as tree,
            tempfile.TemporaryDirectory() as work,
        ):
            backend = Path(tree) / "backend"
            backend.mkdir()
            # The stub fails on import on purpose: this case pins *where* the reading goes,
            # not the measurement. rc 1 is the expected outcome of a failing fixture backend.
            (backend / "rag_chain.py").write_text(
                "raise RuntimeError('fixture backend')\n", encoding="utf-8"
            )
            env = dict(os.environ)
            env.update(
                {
                    self.OVERRIDE: evidence,
                    "PYTHONPATH": str(self.OLD),
                    "TEMP": work,
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                }
            )
            result = subprocess.run(
                [sys.executable, str(self.OLD / "b_probe_app_paths.py"), "qa", tree],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr[-400:])
            written = list(Path(evidence).glob("b-probe-readings-app-*.json"))
            self.assertEqual(len(written), 1, [str(p) for p in written])
            payload = json.loads(written[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "app-paths")
            self.assertEqual(self.dir_state(), before)


if __name__ == "__main__":
    unittest.main()
