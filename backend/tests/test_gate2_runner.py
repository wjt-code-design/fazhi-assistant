"""V2-T6（2026-09-09）：gate2_runner 长跑可靠性——假 HTTP 服务离线测试（零真实模型调用）。

覆盖：唯一 run 占用/禁覆盖、逐题原子 checkpoint、resume 跳过已完成、CLIENT_TIMEOUT
暂停队列与 unknown_server_state 双门禁、HTTP 错误保留、非 SSE 记录。
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import scripts.gate2_runner as runner

INITIAL_OK_FINAL_SSE = (
    'data: {"type": "agent_status", "status": "completed"}\n\n'
    'data: {"type": "verification", "verdict": "PASS"}\n\n'
    'data: {"type": "token", "content": "已确认事实：\\n- 双方签署借款合同\\n\\n可执行建议与风险提示：\\n依据《民法典》第675条处理。"}\n\n'
    'data: {"type": "final", "run_id": "agent-run-x", "state_version": 6}\n\n'
    "data: [DONE]\n\n"
)
CLARIFY_SSE = (
    'data: {"type": "clarification", "prompt": "公司的内网安全制度有什么要求？",'
    ' "run_id": "agent-run-x", "state_version": 3, "conversation_id": 7}\n\n'
    "data: [DONE]\n\n"
)
SCOPE_CLARIFY_SSE = (
    'data: {"type": "clarification", "prompt": "本次请求分解出 8 个法律争点，超过单次可处理上限 5 个。'
    '请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\\n1. 争点甲\\n2. 争点乙",'
    ' "run_id": "agent-run-x", "state_version": 3, "conversation_id": 7}\n\n'
    "data: [DONE]\n\n"
)


class _FakeGateService:
    """可控假 HTTP 服务：按 case 注入场景；记录全部 chat 请求。"""

    def __init__(self) -> None:
        self.chat_requests: list[dict] = []
        self.initial_scene: dict[str, str] = {}  # case_id → scene
        self._lock = threading.Lock()

    def set_scene(self, case_id: str, scene: str) -> None:
        self.initial_scene[case_id] = scene

    def start(self) -> ThreadingHTTPServer:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # 静默
                pass

            def _send_sse(self, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/auth/login":
                    self._send_sse("SYNC")  # runner 只取 json token
                    return
                if self.path != "/api/chat":
                    self.send_error(404)
                    return
                # login 的响应不是 JSON 会让 runner 失败——单独处理 login：
                with service._lock:
                    service.chat_requests.append(dict(payload))
                content = str(payload.get("content", ""))
                case_id = next((cid for cid, c in runner.BY_ID.items() if c["initial_question"] == content), None)
                scene = service.initial_scene.get(case_id, "final")
                if scene == "http_500":
                    body = b'{"detail": "internal error"}'
                    self.send_response(500)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if scene == "timeout":
                    self.close_connection = True  # 不响应直接断开 → 客户端 OSError
                    return
                if scene == "hang":
                    import time as _time

                    _time.sleep(15)  # 挂起：模拟长请求，供"中途 kill 进程"测试窗口
                    self._send_sse(INITIAL_OK_FINAL_SSE)
                    return
                if scene == "non_sse":
                    body = b"plain text, not an SSE stream"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if scene == "clarify_once":
                    self._send_sse(CLARIFY_SSE)
                    return
                if scene == "scope":
                    self._send_sse(SCOPE_CLARIFY_SSE)
                    return
                self._send_sse(INITIAL_OK_FINAL_SSE)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # login 单独返回 JSON token（覆盖上面 SSE 行为）：
        original_do_post = Handler.do_POST

        def do_POST(self):  # noqa: N802
            if self.path == "/api/auth/login":
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                body = b'{"token": "test-token"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            original_do_post(self)

        Handler.do_POST = do_POST
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "EVID", tmp_path)
    service = _FakeGateService()
    server = service.start()
    yield tmp_path, service, server.server_port
    server.shutdown()
    server.server_close()


def _run(harness, *extra: str) -> int:
    _tmp, _service, port = harness
    # parse_args(argv) 的 argv 不含程序名
    argv = ["--run", "t6-run", "--base-url", f"http://127.0.0.1:{port}", *extra]
    return runner.run(argv)


def test_two_cases_complete_outputs_written_and_rerun_refuses(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "clarify_once")  # C01: 澄清一轮（关键词"内网"命中事实）→ final
    service.set_scene("C02", "final")

    assert _run(harness, "--case", "C01,C02") == 0

    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((tmp_path / "gate2-run-t6-run-checkpoint.json").read_text(encoding="utf-8"))
    assert set(sessions["results"]) == {"C01", "C02"}
    assert all(r["agent_completed"] is True for r in sessions["results"].values())
    assert sessions["results"]["C01"]["final_chars"] > 0
    assert set(checkpoint["results"]) == {"C01", "C02"}
    assert not list(tmp_path.glob("*.tmp"))  # 原子写无残留

    # 旧 run 禁止覆盖：重跑同 run 直接拒绝且产物不变
    before = sessions
    assert _run(harness, "--case", "C01,C02") == 4
    after = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert after == before


def test_create_refuses_when_claim_already_exists(harness):
    tmp_path, _service, _port = harness
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )

    assert _run(harness, "--case", "C01") == 4


def test_resume_skips_completed_cases_without_reissuing_requests(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "final")

    assert _run(harness, "--case", "C01") == 0
    requests_after_first = len(service.chat_requests)

    # resume 同一题：已完成 → 跳过，不向服务端重发（防重复计费）
    assert _run(harness, "--resume", "--case", "C01") == 0
    assert len(service.chat_requests) == requests_after_first
    # nothing-to-do 分支幂等补写最终产物：sessions 必存在且结果与首次一致
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["agent_completed"] is True


def test_client_timeout_pauses_queue_and_marks_unknown(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "timeout")
    service.set_scene("C02", "final")

    exit_code = _run(harness, "--case", "C01,C02")
    assert exit_code == 3  # 暂停队列，非失败也非成功
    chat_initials = [r for r in service.chat_requests if r.get("content") == runner.BY_ID["C02"]["initial_question"]]
    assert chat_initials == []  # 未自动发下一题
    checkpoint = json.loads((tmp_path / "gate2-run-t6-run-checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["results"]["C01"]["unknown_server_state"] is True
    assert not (tmp_path / "gate2-run-t6-run-sessions.json").exists()


def test_resume_refuses_unknown_without_manual_confirmation(harness):
    tmp_path, _service, _port = harness
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )
    (tmp_path / "gate2-run-t6-run-checkpoint.json").write_text(
        json.dumps(
            {"run": "t6-run", "targets": ["C01"], "results": {"C01": {"unknown_server_state": True, "rounds": []}}}
        ),
        encoding="utf-8",
    )

    assert _run(harness, "--resume", "--case", "C01") == 5


def test_resume_with_retry_unknown_reruns_marked_case(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "final")
    (tmp_path / "gate2-run-t6-run.claim.json").write_text(
        json.dumps({"run": "t6-run", "targets": ["C01"]}), encoding="utf-8"
    )
    (tmp_path / "gate2-run-t6-run-checkpoint.json").write_text(
        json.dumps(
            {"run": "t6-run", "targets": ["C01"], "results": {"C01": {"unknown_server_state": True, "rounds": []}}}
        ),
        encoding="utf-8",
    )
    before = len(service.chat_requests)

    assert _run(harness, "--resume", "--retry-unknown", "--case", "C01") == 0
    assert len(service.chat_requests) > before  # 显式确认后重跑
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["agent_completed"] is True
    assert "unknown_server_state" not in sessions["results"]["C01"]


def test_http_error_is_recorded_and_queue_continues(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "http_500")
    service.set_scene("C02", "final")

    assert _run(harness, "--case", "C01,C02") == 0
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert sessions["results"]["C01"]["rounds"][0]["status"] == 500
    assert sessions["results"]["C01"]["agent_completed"] is False
    assert sessions["results"]["C02"]["agent_completed"] is True  # HTTP 错误是确定结果，不阻塞队列


def test_non_sse_response_is_recorded_without_agent_completion(harness):
    tmp_path, service, _port = harness
    service.set_scene("C01", "non_sse")

    assert _run(harness, "--case", "C01") == 0
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    r = sessions["results"]["C01"]
    assert r["final_chars"] == 0
    assert r["agent_completed"] is False  # final_chars>0 不得替代持久化成功；此处两者皆无


def _subprocess_run(harness, *extra: str, capture: bool = False):
    """子进程真实运行 runner（--out-dir 隔离产物，不经 monkeypatch）。"""
    _tmp, _service, port = harness
    argv = [
        sys.executable,
        "scripts/gate2_runner.py",
        "--run",
        "t6-run",
        "--base-url",
        f"http://127.0.0.1:{port}",
        "--out-dir",
        str(_tmp),
        *extra,
    ]
    if capture:
        return subprocess.run(argv, cwd=".", capture_output=True, text=True, timeout=60)
    return subprocess.Popen(argv, cwd=".", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_mid_run_process_kill_recovers_from_checkpoint(harness):
    """显式模拟"中途进程退出"（教学手册第七课）：C01 完成后进程被杀——
    checkpoint 保留 C01、sessions 不存在；resume 恢复并完成 C02。"""
    import time as _time

    tmp_path, service, port = harness
    service.set_scene("C01", "final")
    service.set_scene("C02", "hang")

    proc = _subprocess_run(harness, "--case", "C01,C02")
    checkpoint = tmp_path / "gate2-run-t6-run-checkpoint.json"
    deadline = _time.monotonic() + 20
    while _time.monotonic() < deadline:
        if checkpoint.exists():
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            if "C01" in data.get("results", {}):
                break
        _time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("checkpoint 未在时限内出现 C01")
    proc.kill()
    proc.wait(timeout=10)

    # 进程退出后的现场：C01 已在 checkpoint，最终产物不存在，run 仍被 claim 占用
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert "C01" in saved["results"] and "C02" not in saved["results"]
    assert not (tmp_path / "gate2-run-t6-run-sessions.json").exists()
    assert (tmp_path / "gate2-run-t6-run.claim.json").exists()

    # create 重入被拒；resume 恢复并完成 C02
    service.set_scene("C02", "final")
    create_rejected = _subprocess_run(harness, "--case", "C01,C02", capture=True)
    assert create_rejected.returncode == 4
    resumed = _subprocess_run(harness, "--resume", "--case", "C01,C02", capture=True)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    sessions = json.loads((tmp_path / "gate2-run-t6-run-sessions.json").read_text(encoding="utf-8"))
    assert set(sessions["results"]) == {"C01", "C02"}
    assert all(r["agent_completed"] is True for r in sessions["results"].values())


# ---- 2026-09-13 题集自包含 fact_reveal（v2 新案例接入；付费基线授权）----

_V2_CASE = {
    "id": "E01",
    "fact_reveal": {
        "r1": [{"text": "合同与对账单齐全", "keywords": ["合同", "对账"]}],
        "r2": [{"text": "去年12月发过催款函", "keywords": ["催款", "函"]}],
        "bad": [{"text": "非法轮次键", "keywords": ["x"]}],
    },
}


def test_facts_from_case_set_extends_and_protects_base():
    base = {"C01-r1-f1": {"round": 1, "keywords": ["内网"], "text": "旧文本"}}
    facts = runner._facts_from_case_set(base, [{"id": "C01"}, _V2_CASE])
    assert facts["C01-r1-f1"]["text"] == "旧文本"  # fid 冲突 base 优先（v1 冻结零变化）
    assert facts["E01-r1-f1"] == {"round": 1, "keywords": ["合同", "对账"], "text": "合同与对账单齐全"}
    assert facts["E01-r2-f1"]["round"] == 2
    assert not [fid for fid in facts if "bad" in fid]  # 非法轮次键跳过
    assert "E01-r1-f1" not in base  # 不变更入参


def test_fact_reveal_round_isolation_via_shared_matcher():
    facts = runner._facts_from_case_set({}, [_V2_CASE])
    res = runner.match_revealable_facts(
        case_id="E01", prompt="当时签合同和送货对账了吗？", current_round=1, answered_fact_ids=set(), facts=facts
    )
    assert [m["fact_id"] for m in res.matched_facts] == ["E01-r1-f1"]  # 未来轮不提前披露
    res2 = runner.match_revealable_facts(
        case_id="E01", prompt="你们后来催款过吗？", current_round=2, answered_fact_ids={"E01-r1-f1"}, facts=facts
    )
    assert [m["fact_id"] for m in res2.matched_facts] == ["E01-r2-f1"]


def test_scope_clarification_replies_issue_numbers_not_no_match_reply(harness):
    """范围选择澄清（争点>上限）：runner 必须答编号选择；NO_MATCH_REPLY 会被服务端 409。"""
    tmp_path, service, _port = harness
    service.set_scene("C01", "scope")

    assert _run(harness, "--case", "C01") == 0
    resumes = [r for r in service.chat_requests if r.get("agent_run_id")]
    assert resumes, "scope 澄清后应有 resume 请求"
    assert resumes[0]["content"] == runner.SCOPE_REPLY
    assert all(r.get("content") != runner.NO_MATCH_REPLY for r in resumes)
