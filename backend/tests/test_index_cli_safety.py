"""D-14 CLI safety: real subprocess entry, isolated Chroma, no application startup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCRIPTS = ("import_docs", "backfill_time_meta", "eval_chunking", "verify_new_law")

CHILD = r"""
import importlib.abc
import json
import os
import runpy
import socket
import sys
import types
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
backend = Path(os.environ["D14_BACKEND"])
sys.path[:0] = [str(backend), str(backend / "tests")]
mode = os.environ["D14_MODE"]
script = os.environ["D14_SCRIPT"]

def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if path.name.startswith(".env") or path == backend / "app.db":
            raise RuntimeError("FORBIDDEN_PRIVATE_FILE")
        if any(path == backend / part or backend / part in path.parents
               for part in ("data", "chroma_db", "media", "backups")):
            raise RuntimeError("FORBIDDEN_PRIVATE_DIRECTORY")
sys.addaudithook(audit)

def deny_network(*args, **kwargs):
    raise RuntimeError("NETWORK_DISABLED")
socket.socket.connect = deny_network
socket.create_connection = deny_network

if mode in ("import", "guard", "help"):
    class NoRuntimeImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in ("rag_chain", "knowledge_service", "retrieval", "dotenv"):
                raise RuntimeError("EARLY_RUNTIME_IMPORT:" + fullname)
    sys.meta_path.insert(0, NoRuntimeImports())
else:
    # Replace only model loading. The scripts, ORM-free services and Chroma run for real.
    from _fake_embeddings import FakeEmbeddings
    fake_hf = types.ModuleType("langchain_huggingface")
    class CliEmbeddings(FakeEmbeddings):
        def embed_query(self, text):
            if mode == "fault":
                raise RuntimeError("D14_QUERY_FAILURE")
            return super().embed_query(text)
    fake_hf.HuggingFaceEmbeddings = lambda **kwargs: CliEmbeddings()
    sys.modules["langchain_huggingface"] = fake_hf
    target = os.environ["CHROMA_DIR"]
    if mode != "isolated":
        import chromadb
        client = chromadb.PersistentClient(path=target)
        col = client.get_or_create_collection("legal_provisions_cos", metadata={"hnsw:space": "cosine"})
        col.add(ids=["sentinel"], documents=["合成旧条文"], embeddings=[[0.1] * 768],
                metadatas=[{"source": "合成旧法", "article": "第一条", "custom": "keep"}])
    if script in ("eval_chunking", "verify_new_law"):
        from contextlib import contextmanager
        from scripts import chroma_dir_guard
        original_isolation = chroma_dir_guard.isolated_chroma
        @contextmanager
        def observe_private_store(caller):
            with original_isolation(caller) as chosen:
                try:
                    yield chosen
                finally:
                    if "rag_chain" in sys.modules:
                        print("D14_PRIVATE=" + json.dumps(sys.modules["rag_chain"].vectorstore._collection.get()))
        chroma_dir_guard.isolated_chroma = observe_private_store

before_cwd = os.getcwd()
def execute_script(name):
    baseline = os.environ.get("D14_BASELINE")
    if baseline:
        import subprocess
        code = subprocess.run(["git", "-C", str(backend), "show",
                               baseline + ":backend/scripts/" + script + ".py"],
                              check=True, capture_output=True).stdout.decode("utf-8-sig")
        exec(compile(code, str(backend / "scripts" / (script + ".py")), "exec"),
             {"__name__": name, "__file__": str(backend / "scripts" / (script + ".py"))})
    else:
        runpy.run_module("scripts." + script, run_name=name)
if mode == "import":
    execute_script("d14_import_probe")
    assert os.getcwd() == before_cwd, "IMPORT_CHANGED_CWD"
    print("PURE_IMPORT_OK")
else:
    sys.argv = [script, *json.loads(os.environ["D14_ARGS"])]
    code = 0
    try:
        execute_script("__main__")
    except SystemExit as exc:
        if isinstance(exc.code, int):
            code = exc.code
        elif exc.code is not None:
            print(str(exc.code), file=sys.stderr)
            code = 1
    except Exception as exc:
        if mode != "fault":
            raise
        print("D14_EXCEPTION=" + str(exc))
        code = 3
    if mode in ("run", "fault"):
        print("D14_RESULT=" + json.dumps(col.get(include=["metadatas", "documents"]), ensure_ascii=False))
        print("D14_TARGET=" + os.environ["CHROMA_DIR"])
        print("D14_EXIT=" + str(code))
    if mode == "isolated":
        assert os.getcwd() == before_cwd, "CLI_DID_NOT_RESTORE_CWD"
        print("D14_CWD_RESTORED")
    raise SystemExit(code)
"""


def run_script(tmp_path: Path, script: str, args: list[str], *, mode="guard", target=True):
    lane = tmp_path / "lane"
    lane.mkdir(exist_ok=True)
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
    env.update(
        D14_BACKEND=str(BACKEND),
        D14_SCRIPT=script,
        D14_MODE=mode,
        D14_ARGS=json.dumps(args),
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        EMBEDDING_PROVIDER="local",
        RERANK_ENABLED="false",
        EMBEDDING_QUOTA_TOTAL="0",
        RERANK_QUOTA_TOTAL="0",
        HF_HUB_OFFLINE="1",
        ANONYMIZED_TELEMETRY="False",
        QUOTA_DB=str(lane / "quota.sqlite"),
        DATABASE_URL="sqlite:///" + (lane / "app.db").as_posix(),
        USERPROFILE=str(lane),
    )
    if target:
        env["CHROMA_DIR"] = str(lane / "explicit-chroma")
    if os.environ.get("D14_BASELINE"):
        env["D14_BASELINE"] = os.environ["D14_BASELINE"]
    return subprocess.run(
        [sys.executable, "-B", "-I", "-c", CHILD],
        cwd=lane,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=90,
    )


def result(proc):
    line = next(line for line in proc.stdout.splitlines() if line.startswith("D14_RESULT="))
    return json.loads(line.removeprefix("D14_RESULT="))


@pytest.mark.parametrize("script", SCRIPTS)
def test_import_is_pure_and_keeps_cwd(tmp_path, script):
    proc = run_script(tmp_path, script, [], mode="import", target=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PURE_IMPORT_OK" in proc.stdout
    assert list((tmp_path / "lane").iterdir()) == []


@pytest.mark.parametrize("script", SCRIPTS)
def test_help_does_not_initialize_runtime(tmp_path, script):
    proc = run_script(tmp_path, script, ["--help"], mode="help", target=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "usage:" in proc.stdout
    assert list((tmp_path / "lane").iterdir()) == []


@pytest.mark.parametrize("script", ("import_docs", "backfill_time_meta"))
@pytest.mark.parametrize("args", ([], ["--write"]))
def test_missing_target_refused_before_runtime_or_input(tmp_path, script, args):
    proc = run_script(tmp_path, script, args, target=False)
    assert proc.returncode != 0
    assert "require_explicit_target" in proc.stderr, proc.stdout + proc.stderr
    assert "EARLY_RUNTIME_IMPORT" not in proc.stderr
    assert list((tmp_path / "lane").iterdir()) == []


@pytest.mark.parametrize("script", ("import_docs", "backfill_time_meta"))
def test_conflicting_write_and_dry_run_refused_before_runtime(tmp_path, script):
    proc = run_script(tmp_path, script, ["--write", "--dry-run"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "not allowed with argument" in proc.stderr
    assert "EARLY_RUNTIME_IMPORT" not in proc.stderr


@pytest.mark.parametrize("write", (False, True))
def test_backfill_defaults_to_preview_and_preserves_other_metadata(tmp_path, write):
    proc = run_script(tmp_path, "backfill_time_meta", ["--write"] if write else [], mode="run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = result(proc)
    assert data["ids"] == ["sentinel"]
    meta = data["metadatas"][0]
    assert meta["custom"] == "keep"
    assert meta["source"] == "合成旧法"
    if write:
        assert {key: meta[key] for key in ("status", "effective_from", "effective_to")} == {
            "status": "未验证",
            "effective_from": "",
            "effective_to": "",
        }
    else:
        assert "status" not in meta
        assert "dry-run" in proc.stdout


@pytest.mark.parametrize("write", (False, True))
def test_import_docs_uses_selected_input_and_only_writes_explicitly(tmp_path, write):
    inputs = tmp_path / "clean"
    inputs.mkdir()
    (inputs / "中华人民共和国合成导入法_20200101.txt").write_text(
        "第一条 为了检验入口安全，制定本合成条文。\n\n第二条 本合成规则只供测试。\n", encoding="utf-8"
    )
    args = ["--dir", str(inputs)] + (["--write"] if write else [])
    proc = run_script(tmp_path, "import_docs", args, mode="run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = result(proc)
    assert "sentinel" in data["ids"]
    imported = [m for m in data["metadatas"] if m.get("source") == "合成导入法"]
    assert len(imported) == (2 if write else 0)
    assert next(m for m in data["metadatas"] if m["source"] == "合成旧法")["custom"] == "keep"


@pytest.mark.parametrize("script", ("eval_chunking", "verify_new_law"))
def test_evaluation_uses_private_target_and_preserves_external_store(tmp_path, script, record_property):
    proc = run_script(tmp_path, script, [], mode="run")
    assert "D14_RESULT=" in proc.stdout, proc.stdout + proc.stderr
    assert result(proc)["ids"] == ["sentinel"]
    assert "临时知识库：" in proc.stdout
    chosen = next(
        line.removeprefix("临时知识库：") for line in proc.stdout.splitlines() if line.startswith("临时知识库：")
    )
    assert Path(chosen) != tmp_path / "lane" / "explicit-chroma"
    assert "EARLY_RUNTIME_IMPORT" not in proc.stderr
    assert "FORBIDDEN_PRIVATE" not in proc.stderr
    # Random fixed embeddings check storage wiring, not legal retrieval quality.
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    record_property("synthetic_measurement_exit", proc.returncode)
    record_property("synthetic_measurement_stdout", proc.stdout)
    private = next(
        line.removeprefix("D14_PRIVATE=") for line in proc.stdout.splitlines() if line.startswith("D14_PRIVATE=")
    )
    assert json.loads(private)["ids"] == [], "合成评测条文未清理"


@pytest.mark.parametrize("script", ("eval_chunking", "verify_new_law"))
def test_evaluation_failure_still_removes_private_rows_and_restores_target(tmp_path, script):
    proc = run_script(tmp_path, script, [], mode="fault")
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "D14_EXCEPTION=D14_QUERY_FAILURE" in proc.stdout
    assert result(proc)["ids"] == ["sentinel"]
    private = next(
        line.removeprefix("D14_PRIVATE=") for line in proc.stdout.splitlines() if line.startswith("D14_PRIVATE=")
    )
    assert json.loads(private)["ids"] == []
    assert "D14_TARGET=" + str(tmp_path / "lane" / "explicit-chroma") in proc.stdout


@pytest.mark.parametrize("script", ("eval_chunking", "verify_new_law"))
def test_evaluation_does_not_read_implicit_dotenv_in_caller_directory(tmp_path, script):
    lane = tmp_path / "lane"
    lane.mkdir()
    (lane / ".env").write_text("D14_SYNTHETIC_ONLY=1\nEMBEDDING_PROVIDER=cloud\n", encoding="utf-8")
    # Unlike the sentinel tests, do not pre-import Chroma outside the real CLI.
    proc = run_script(tmp_path, script, [], mode="isolated")
    assert proc.returncode in (0, 1), proc.stdout + proc.stderr
    assert "FORBIDDEN_PRIVATE" not in proc.stderr, proc.stdout + proc.stderr
    assert "D14_CWD_RESTORED" in proc.stdout
    private = next(
        line.removeprefix("D14_PRIVATE=") for line in proc.stdout.splitlines() if line.startswith("D14_PRIVATE=")
    )
    assert json.loads(private)["ids"] == []
    assert not (lane / "explicit-chroma").exists()


@pytest.mark.parametrize("write", (False, True))
def test_purge_requires_write_and_keeps_preview_rows(tmp_path, write):
    inputs = tmp_path / "clean"
    inputs.mkdir()
    (inputs / "合成导入法.txt").write_text("第一条 本条文用于测试清理入口。", encoding="utf-8")
    args = ["--dir", str(inputs), "--purge-source", "合成旧法"] + (["--write"] if write else [])
    proc = run_script(tmp_path, "import_docs", args, mode="run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ("sentinel" in result(proc)["ids"]) is not write


def guard_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("d14_guard", BACKEND / "scripts" / "chroma_dir_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("chosen", (None, "", " ", "\t"))
def test_explicit_target_rejects_absent_or_blank_value(monkeypatch, chosen):
    if chosen is None:
        monkeypatch.delenv("CHROMA_DIR", raising=False)
    else:
        monkeypatch.setenv("CHROMA_DIR", chosen)
    with pytest.raises(SystemExit, match="require_explicit_target"):
        guard_module().require_explicit_target("test")


def test_explicit_target_rejects_preloaded_different_store(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chosen"))
    monkeypatch.setitem(sys.modules, "rag_chain", SimpleNamespace(CHROMA_DIR=str(tmp_path / "already-bound")))
    with pytest.raises(SystemExit, match="已初始化的知识库与目标不同"):
        guard_module().require_explicit_target("test")


def test_explicit_target_resolves_relative_path_before_initialization(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CHROMA_DIR", "chosen")
    monkeypatch.delitem(sys.modules, "rag_chain", raising=False)
    assert guard_module().require_explicit_target("test") == str(tmp_path / "chosen")
    assert os.environ["CHROMA_DIR"] == str(tmp_path / "chosen")
    assert not (tmp_path / "chosen").exists()


@pytest.mark.parametrize("loaded", ("settings", "rag_chain", "retrieval", "knowledge_service"))
def test_isolation_refuses_preloaded_runtime_before_changing_env(monkeypatch, loaded):
    monkeypatch.setenv("CHROMA_DIR", "keep-target")
    monkeypatch.setitem(sys.modules, loaded, SimpleNamespace())
    with pytest.raises(SystemExit, match="isolated_chroma"):
        with guard_module().isolated_chroma("test"):
            pytest.fail("preloaded runtime was accepted")
    assert os.environ["CHROMA_DIR"] == "keep-target"


@pytest.mark.parametrize("exit_kind", ("normal", "error", "exit-zero", "exit-one"))
def test_locked_temporary_directory_is_reported_on_every_exit(monkeypatch, tmp_path, capsys, exit_kind):
    from contextlib import contextmanager

    guard = guard_module()
    lane = tmp_path / "locked-lane"
    lane.mkdir()
    cleanup_attempts = []

    @contextmanager
    def locked_directory(**kwargs):
        try:
            yield str(lane)
        finally:
            cleanup_attempts.append(True)  # Model Windows cleanup blocked by an open Chroma handle.

    monkeypatch.setattr(guard.tempfile, "TemporaryDirectory", locked_directory)
    for name in ("settings", "rag_chain", "retrieval", "knowledge_service"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setenv("CHROMA_DIR", "keep-target")
    error = {
        "normal": None,
        "error": RuntimeError("body-failed"),
        "exit-zero": SystemExit(0),
        "exit-one": SystemExit(1),
    }[exit_kind]
    caught = None
    original_cwd = os.getcwd()
    try:
        with guard.isolated_chroma("test"):
            assert os.environ["CHROMA_DIR"] == str(lane / "chroma")
            assert os.getcwd() == str(lane)
            if error is not None:
                raise error
    except (RuntimeError, SystemExit) as exc:
        caught = exc
    assert caught is error, "Cleanup must preserve the original exception or exit code."
    assert cleanup_attempts == [True]
    assert os.environ["CHROMA_DIR"] == "keep-target"
    assert os.getcwd() == original_cwd
    assert "进程退出后可清理：" + str(lane) in capsys.readouterr().err
